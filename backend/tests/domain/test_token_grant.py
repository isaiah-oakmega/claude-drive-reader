"""B3：/token 只接受兩種請求形狀，其他一律拒絕。"""

import pytest
from pydantic import TypeAdapter, ValidationError

from token_broker.domain.token_grant import (
    AuthorizationCodeGrant,
    RefreshTokenGrant,
    TokenGrant,
)

VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"  # RFC 7636 附錄 B 的範例
adapter = TypeAdapter(TokenGrant)


def test_authorization_code_grant_is_accepted() -> None:
    grant = adapter.validate_python(
        {"grant_type": "authorization_code", "code": "4/abc", "code_verifier": VERIFIER}
    )

    assert isinstance(grant, AuthorizationCodeGrant)


def test_refresh_token_grant_is_accepted() -> None:
    grant = adapter.validate_python({"grant_type": "refresh_token", "refresh_token": "1//xyz"})

    assert isinstance(grant, RefreshTokenGrant)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"grant_type": "client_credentials"},
        {"grant_type": "password", "username": "a", "password": "b"},
        {"grant_type": "authorization_code", "code": "4/abc"},  # 缺 code_verifier
        {"grant_type": "authorization_code", "code": "", "code_verifier": VERIFIER},
        {"grant_type": "authorization_code", "code": "4/abc", "code_verifier": "too-short"},
        {"grant_type": "refresh_token"},
        {"grant_type": "refresh_token", "refresh_token": ""},
        # 本機不能指定 scope 或 redirect_uri（B4、B5），多出的欄位一律拒絕
        {"grant_type": "refresh_token", "refresh_token": "1//xyz", "scope": "https://www.googleapis.com/auth/drive"},
        {"grant_type": "authorization_code", "code": "4/abc", "code_verifier": VERIFIER, "redirect_uri": "https://evil.example"},
    ],
)
def test_other_shapes_are_rejected(body: dict) -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python(body)
