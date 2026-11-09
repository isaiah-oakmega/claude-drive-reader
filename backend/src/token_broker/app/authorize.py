"""Use case：把本機的授權請求轉成 Google 授權網址。"""

from token_broker.domain.code_relay import RelayState
from token_broker.domain.pkce import CodeChallenge
from token_broker.infra.google_oauth import GoogleOAuthClient


def build_authorization_redirect(oauth: GoogleOAuthClient, state: str, code_challenge: str) -> str:
    # 先驗證兩個參數的格式，任何一個不合就丟出領域例外，由 api 層回 400 錯誤頁。
    # 本機只能提供 state 與 code_challenge；client_id、redirect_uri、scope 都由 Broker 決定（B4、B5）。
    return oauth.authorization_url(RelayState.parse(state), CodeChallenge.parse(code_challenge))
