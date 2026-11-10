"""authorize、auth_status、logout 三個 use case（A1、A2、A6，以及 Q1 的「上一次授權的結果」）。"""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path

from local_authorization.app.token_provider import AccessTokenProvider
from local_authorization.domain.attempt import AttemptResult, AuthorizationAttempt, CodeReceived
from local_authorization.domain.credential import LocalCredential, RevokeOutcome
from local_authorization.domain.errors import AuthorizationError, CallbackPortUnavailable
from local_authorization.domain.limits import ATTEMPT_TTL_SECONDS
from local_authorization.infra.broker_client import BrokerClient
from local_authorization.infra.credential_store import CredentialStore
from local_authorization.infra.google_revoke import GoogleRevoker
from local_authorization.infra.loopback_listener import LoopbackListener


@dataclass(frozen=True)
class AuthorizationStarted:
    url: str
    browser_opened: bool
    expires_in_seconds: float


@dataclass(frozen=True)
class AuthStatus:
    authorized: bool
    account: str | None
    attempt_in_progress: bool
    # 本次 process 最近一次結束的 Attempt 的結果；還沒嘗試過時為 None
    last_result: AttemptResult | None
    credentials_path: Path
    permissions_enforced: bool


@dataclass(frozen=True)
class LogoutReport:
    had_credential: bool
    revoke: RevokeOutcome | None
    deleted: bool


class AuthorizationService:
    def __init__(
        self,
        *,
        broker: BrokerClient,
        store: CredentialStore,
        tokens: AccessTokenProvider,
        revoker: GoogleRevoker,
        listen: Callable[[int | None], LoopbackListener] = LoopbackListener.bind,
        open_browser: Callable[[str], bool],
        callback_port: int | None,
        clock: Callable[[], float] = time.monotonic,
        utc_now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._broker = broker
        self._store = store
        self._tokens = tokens
        self._revoker = revoker
        self._listen = listen
        self._open_browser = open_browser
        self._callback_port = callback_port
        self._clock = clock
        self._utc_now = utc_now
        self._attempt: AuthorizationAttempt | None = None
        self._listener: LoopbackListener | None = None
        self._last_result: AttemptResult | None = None
        # tool 呼叫與 listener 的 callback 在不同 thread；鎖只保護上面三個欄位的轉換，
        # 不在持有鎖時做網路呼叫或關閉 listener，避免和 listener 的 thread 互相等待
        self._lock = threading.Lock()

    # ---------- authorize ----------

    def authorize(self) -> AuthorizationStarted:
        # A1：同時最多一個 Attempt。先關掉舊的 listener，固定 port 時新的才綁得上去
        with self._lock:
            previous, self._listener, self._attempt = self._listener, None, None
        if previous is not None:
            previous.close()

        try:
            listener = self._listen(self._callback_port)
        except OSError as error:
            raise CallbackPortUnavailable(self._callback_port) from error
        now = self._clock()
        try:
            attempt = AuthorizationAttempt.start(port=listener.port, now=now)
        except ValueError as error:
            # OS 分配的 port 理論上一定在 1024 以上；真的不在 B2 的範圍內就放棄，Broker 也不會接受
            listener.close()
            raise CallbackPortUnavailable(listener.port) from error

        with self._lock:
            # 兩個 authorize 同時執行時，後到的保留，先到的關掉
            superseded, self._listener, self._attempt = self._listener, listener, attempt
        if superseded is not None:
            superseded.close()
        listener.serve(
            partial(self._handle_callback, attempt),
            timeout_seconds=attempt.seconds_left(now),
            on_timeout=partial(self._expire, attempt),
        )

        url = self._broker.authorization_url(attempt.state, attempt.pkce.challenge)
        return AuthorizationStarted(url=url, browser_opened=self._open_browser(url), expires_in_seconds=ATTEMPT_TTL_SECONDS)

    def _handle_callback(self, attempt: AuthorizationAttempt, params: dict[str, str]) -> AttemptResult | None:
        """在 listener 的 thread 執行。回傳 None 時 listener 回 400 並繼續等（A2）。"""
        with self._lock:
            if attempt is not self._attempt:
                # 已被新的 authorize 取代（A1）
                return None
            verdict = attempt.receive_callback(params, self._clock())
            if not isinstance(verdict, CodeReceived):
                if attempt.result is not None:
                    self._last_result = attempt.result
                return verdict

        ok = self._complete(verdict.code, attempt.pkce.verifier)
        with self._lock:
            attempt.finish_exchange(ok)
            self._last_result = attempt.result
        return attempt.result

    def _complete(self, code: str, verifier: str) -> bool:
        try:
            issued = self._broker.exchange_code(code, verifier)
            if not issued.refresh_token:
                # 有 prompt=consent 時 Google 一定會給；沒給就無法保存授權，視為失敗
                return False
            self._store.save(
                LocalCredential(
                    refresh_token=issued.refresh_token,
                    scope=issued.scope,
                    obtained_at=self._utc_now().isoformat(timespec="seconds"),
                )
            )
        except (AuthorizationError, OSError):
            # 換不到 token 或寫不進檔案：原本的 Local Credential 保持不變
            return False
        self._tokens.adopt(issued)
        return True

    def _expire(self, attempt: AuthorizationAttempt) -> None:
        with self._lock:
            attempt.expire()
            if attempt is self._attempt and attempt.result is AttemptResult.TIMED_OUT:
                self._last_result = AttemptResult.TIMED_OUT

    # ---------- auth_status ----------

    def status(self) -> AuthStatus:
        with self._lock:
            attempt = self._attempt
            if attempt is not None and self._clock() >= attempt.expires_at:
                # 計時器可能還沒觸發（或 thread 排程延遲），狀態以時間為準
                attempt.expire()
                if attempt.result is AttemptResult.TIMED_OUT:
                    self._last_result = AttemptResult.TIMED_OUT
            # 換 token 的那幾秒 result 還是 None，也算進行中
            in_progress = attempt is not None and attempt.result is None
            last_result = self._last_result

        # 先查帳號再看檔案：查帳號可能觸發 refresh，refresh 遇到 invalid_grant 會刪檔（A5）
        account = self._tokens.current_account()
        authorized = self._store.load() is not None
        return AuthStatus(
            authorized=authorized,
            account=account if authorized else None,
            attempt_in_progress=in_progress,
            last_result=last_result,
            credentials_path=self._store.path,
            permissions_enforced=self._store.permissions_enforced,
        )

    # ---------- logout ----------

    def logout(self) -> LogoutReport:
        credential = self._store.load()
        if credential is None:
            self._tokens.forget()
            return LogoutReport(had_credential=False, revoke=None, deleted=False)
        # A6：先 revoke 再刪檔；revoke 失敗也照樣刪，結果如實回報
        outcome = self._revoker.revoke(credential.refresh_token)
        deleted = self._store.delete()
        self._tokens.forget()
        return LogoutReport(had_credential=True, revoke=outcome, deleted=deleted)
