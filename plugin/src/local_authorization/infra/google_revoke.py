"""logout 時撤銷 refresh token（A6）。revoke 不需要 client secret，所以本機直接呼叫 Google，不經過 Broker。"""

import httpx2

from local_authorization.domain.credential import RevokeOutcome

REVOKE_ENDPOINT = "https://oauth2.googleapis.com/revoke"


class GoogleRevoker:
    def __init__(self, http: httpx2.Client) -> None:
        self._http = http

    def revoke(self, token: str) -> RevokeOutcome:
        try:
            # token 放在 form body，不放在網址：網址可能被 proxy 或 log 記下
            response = self._http.post(REVOKE_ENDPOINT, data={"token": token})
        except httpx2.HTTPError:
            return RevokeOutcome.FAILED
        if response.status_code == 200:
            return RevokeOutcome.REVOKED
        if response.status_code == 400:
            # Google 對已撤銷或已過期的 token 回 400 invalid_token：目的已經達成
            return RevokeOutcome.ALREADY_INVALID
        return RevokeOutcome.FAILED
