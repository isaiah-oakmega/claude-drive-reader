"""呼叫 Google OAuth：組授權網址、向 token endpoint 換 token。只有這裡知道 client secret 與 Google 的 HTTP 細節。"""

from urllib.parse import urlencode

import httpx
from pydantic import ValidationError

from token_broker.domain import oauth_policy
from token_broker.domain.code_relay import RelayState
from token_broker.domain.errors import UpstreamRejected, UpstreamUnavailable
from token_broker.domain.pkce import CodeChallenge
from token_broker.domain.token_grant import (
    AuthorizationCodeGrant,
    IssuedToken,
    RefreshTokenGrant,
)

AUTHORIZATION_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# Google 以這兩個狀態碼回報「請求被拒」並附上 OAuth 標準的 error 欄位，例如 invalid_grant、invalid_client。
# 其他狀態碼（5xx、429）代表 Google 暫時無法服務，不是本機請求的問題。
_OAUTH_ERROR_STATUSES = {400, 401}


class GoogleOAuthClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, http: httpx.Client) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        # http 由組裝層建立並設定逾時；測試時換成 MockTransport，不連網
        self._http = http

    def authorization_url(self, state: RelayState, challenge: CodeChallenge) -> str:
        params = {
            "client_id": self._client_id,
            "redirect_uri": self._redirect_uri,
            "response_type": "code",
            "scope": oauth_policy.SCOPE,
            "access_type": oauth_policy.ACCESS_TYPE,
            "prompt": oauth_policy.PROMPT,
            "code_challenge": challenge.value,
            "code_challenge_method": oauth_policy.CODE_CHALLENGE_METHOD,
            # state 原樣帶回：Google 會在 callback 時還給我們，Broker 再從中取出本機 port
            "state": state.value,
        }
        return f"{AUTHORIZATION_ENDPOINT}?{urlencode(params)}"

    def exchange(self, grant: AuthorizationCodeGrant | RefreshTokenGrant) -> IssuedToken:
        form = {"client_id": self._client_id, "client_secret": self._client_secret}
        if isinstance(grant, AuthorizationCodeGrant):
            # redirect_uri 必須和 /authorize 用的完全相同，Google 才會核發 token（B5）
            form |= {
                "grant_type": "authorization_code",
                "code": grant.code,
                "code_verifier": grant.code_verifier,
                "redirect_uri": self._redirect_uri,
            }
        else:
            form |= {"grant_type": "refresh_token", "refresh_token": grant.refresh_token}

        try:
            response = self._http.post(TOKEN_ENDPOINT, data=form)
        except httpx.HTTPError as exc:
            # 連線失敗、逾時都屬於「Google 暫時不可用」；例外訊息不帶出請求內容
            raise UpstreamUnavailable from exc

        if response.status_code == 200:
            try:
                return IssuedToken.model_validate(response.json())
            except (ValueError, ValidationError) as exc:
                raise UpstreamUnavailable from exc

        if response.status_code in _OAUTH_ERROR_STATUSES:
            body = _json_or_none(response)
            if isinstance(body, dict) and isinstance(body.get("error"), str):
                description = body.get("error_description")
                raise UpstreamRejected(body["error"], description if isinstance(description, str) else None)

        raise UpstreamUnavailable


def _json_or_none(response: httpx.Response) -> object:
    try:
        return response.json()
    except ValueError:
        return None
