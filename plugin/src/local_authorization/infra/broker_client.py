"""C1 的消費端：向 Token Broker 換 token 與 refresh。HTTP 狀態碼只在這裡出現，往上只拋領域例外。"""

from urllib.parse import urlencode

import httpx2

from local_authorization.domain.credential import IssuedTokens
from local_authorization.domain.errors import AuthExpired, BrokerUnreachable


class BrokerClient:
    def __init__(self, base_url: str, http: httpx2.Client) -> None:
        # 去掉結尾的 "/"：使用者在 DRIVE_READER_BROKER_URL 多打一個斜線也能用
        self.base_url = base_url.rstrip("/")
        self._http = http

    def authorization_url(self, state: str, code_challenge: str) -> str:
        # 本機只送 state 與 challenge；client_id、scope、redirect_uri 都由 Broker 補上（B4、B5）
        return f"{self.base_url}/authorize?{urlencode({'state': state, 'code_challenge': code_challenge})}"

    def exchange_code(self, code: str, code_verifier: str) -> IssuedTokens:
        # 不重試：auth code 只能用一次，重送只會拿到 invalid_grant
        return self._post_token({"grant_type": "authorization_code", "code": code, "code_verifier": code_verifier})

    def refresh(self, refresh_token: str) -> IssuedTokens:
        return self._post_token({"grant_type": "refresh_token", "refresh_token": refresh_token})

    def _post_token(self, body: dict[str, str]) -> IssuedTokens:
        try:
            response = self._http.post(f"{self.base_url}/token", json=body)
        except httpx2.HTTPError as error:
            raise BrokerUnreachable(self.base_url) from error

        if response.status_code == 400 and _oauth_error(response) == "invalid_grant":
            # Google 判定 refresh token 或 auth code 已失效；重新授權是唯一的解法（A5）
            raise AuthExpired
        if response.status_code != 200:
            # 其他狀況（502 upstream_unavailable、invalid_client 之類的 Broker 設定錯誤、網址打錯的 404）
            # 都不是使用者重新授權能解決的，對使用者來說就是「Broker 現在給不了 token」
            raise BrokerUnreachable(self.base_url)
        tokens = _parse_tokens(response)
        if tokens is None:
            # 200 但不是 C1 的形狀：例如網址指到別的網站，或被公共 Wi-Fi 的登入頁攔截
            raise BrokerUnreachable(self.base_url)
        return tokens


def _oauth_error(response: httpx2.Response) -> str | None:
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return None
    return error if isinstance(error, str) else None


def _parse_tokens(response: httpx2.Response) -> IssuedTokens | None:
    try:
        data = response.json()
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    access_token, expires_in, scope = data.get("access_token"), data.get("expires_in"), data.get("scope")
    refresh_token = data.get("refresh_token")
    # bool 是 int 的子類別，要特別排除，否則 true 會被當成 1 秒
    if not (isinstance(access_token, str) and access_token):
        return None
    if not (isinstance(expires_in, int) and not isinstance(expires_in, bool) and expires_in > 0):
        return None
    if not isinstance(scope, str) or not (refresh_token is None or isinstance(refresh_token, str)):
        return None
    return IssuedTokens(access_token=access_token, expires_in=expires_in, scope=scope, refresh_token=refresh_token or None)
