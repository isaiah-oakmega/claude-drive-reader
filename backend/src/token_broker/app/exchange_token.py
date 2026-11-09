"""Use case：替本機向 Google 換 token 或 refresh。Broker 只轉手，不保存結果（B1）。"""

from token_broker.domain.token_grant import AuthorizationCodeGrant, IssuedToken, RefreshTokenGrant
from token_broker.infra.google_oauth import GoogleOAuthClient


def exchange_token(oauth: GoogleOAuthClient, grant: AuthorizationCodeGrant | RefreshTokenGrant) -> IssuedToken:
    # 刻意不重試：auth code 只能用一次，重送只會得到 invalid_grant（實作規格「Consistency」）。
    # refresh 的重試交給本機決定。
    return oauth.exchange(grant)
