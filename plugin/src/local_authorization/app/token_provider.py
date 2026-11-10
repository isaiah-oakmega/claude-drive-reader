"""C2 Access Token Provider：給 Drive Reading 一個有效的 access token，它不需要知道 token 從哪裡來。"""

import threading
import time
from collections.abc import Callable
from dataclasses import replace

from local_authorization.domain.credential import AccessToken, IssuedTokens
from local_authorization.domain.errors import AuthExpired, AuthorizationError, NotAuthorized
from local_authorization.infra.broker_client import BrokerClient
from local_authorization.infra.credential_store import CredentialStore
from local_authorization.infra.google_account import GoogleAccount


class AccessTokenProvider:
    def __init__(
        self,
        store: CredentialStore,
        broker: BrokerClient,
        account: GoogleAccount,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._store = store
        self._broker = broker
        self._account = account
        # monotonic 不受使用者調整系統時間影響，用來判斷 token 是否快過期
        self._clock = clock
        self._token: AccessToken | None = None
        self._email: str | None = None
        # MCP 的 tool 在 worker thread 執行，授權完成的通知來自 listener 的 thread；
        # 鎖確保同時兩個請求不會各自 refresh，也不會讀到寫一半的狀態
        self._lock = threading.RLock()

    def get_access_token(self) -> str:
        """回傳有效的 access token。可能拋出 NotAuthorized、AuthExpired、BrokerUnreachable。"""
        with self._lock:
            now = self._clock()
            if self._token is not None and self._token.is_fresh(now):
                return self._token.value

            credential = self._store.load()
            if credential is None:
                self._token = None
                raise NotAuthorized
            try:
                issued = self._broker.refresh(credential.refresh_token)
            except AuthExpired:
                # A5：Google 說這個 refresh token 已經沒用了，留著只會讓之後每次都失敗
                self._store.delete()
                self._token = self._email = None
                raise
            self._token = AccessToken.issued(issued.access_token, issued.expires_in, now)
            if issued.refresh_token and issued.refresh_token != credential.refresh_token:
                # Google 換發了新的 refresh token 才寫檔；沒換就不碰檔案（實作規格「Consistency」）
                self._store.save(replace(credential, refresh_token=issued.refresh_token))
            return self._token.value

    def invalidate(self) -> None:
        """Drive 回 401 時呼叫：下一次 get_access_token 一定重新 refresh。

        「每次請求最多重來一次」由呼叫端（Drive Reading）負責，這裡只丟掉快取。
        """
        with self._lock:
            self._token = None

    def current_account(self) -> str | None:
        """目前授權帳號的 email（R6 的訊息與 auth_status 用）。拿不到時回 None，不拋例外。"""
        with self._lock:
            if self._email is not None:
                return self._email
            try:
                token = self.get_access_token()
            except AuthorizationError:
                return None
            self._email = self._account.email(token)
            return self._email

    def adopt(self, issued: IssuedTokens) -> None:
        """授權完成時，直接使用換 code 拿到的 access token。帳號可能換了，所以清掉 email 快取。"""
        with self._lock:
            self._token = AccessToken.issued(issued.access_token, issued.expires_in, self._clock())
            self._email = None

    def forget(self) -> None:
        """logout 後丟掉記憶體中的 token 與 email。"""
        with self._lock:
            self._token = self._email = None
