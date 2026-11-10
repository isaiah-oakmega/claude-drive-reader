"""A3 與 C2 的 refresh 時機：Local Credential 只有 refresh token；access token 只在記憶體，到期前 60 秒視為需要更新。"""

import dataclasses

from local_authorization.domain.credential import AccessToken, LocalCredential
from local_authorization.domain.limits import REFRESH_MARGIN_SECONDS


def test_local_credential_holds_only_refresh_token_scope_and_time() -> None:
    fields = {f.name for f in dataclasses.fields(LocalCredential)}

    assert fields == {"refresh_token", "scope", "obtained_at"}


def test_access_token_is_fresh_until_sixty_seconds_before_expiry() -> None:
    token = AccessToken.issued(value="ya29.x", expires_in=3600, now=1000.0)

    assert REFRESH_MARGIN_SECONDS == 60
    assert token.is_fresh(1000.0 + 3600 - 61)
    assert token.is_fresh(1000.0 + 3600 - 60) is False


def test_short_lived_token_is_never_fresh() -> None:
    # Google 理論上不會發這麼短的 token；就算發了，也只會每次都 refresh，而不是用一個快過期的 token
    token = AccessToken.issued(value="ya29.x", expires_in=30, now=1000.0)

    assert token.is_fresh(1000.0) is False
