"""/authorize 只接受 S256 code_challenge：base64url 編碼的 SHA-256，固定 43 個字元（RFC 7636）。"""

import pytest

from token_broker.domain.errors import InvalidCodeChallenge
from token_broker.domain.pkce import CodeChallenge

VALID = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"  # RFC 7636 附錄 B 的範例


def test_valid_challenge_is_accepted() -> None:
    assert CodeChallenge.parse(VALID).value == VALID


@pytest.mark.parametrize(
    "value",
    [
        "",
        VALID[:-1],  # 42 個字元
        VALID + "A",  # 44 個字元
        VALID[:-1] + "=",  # base64 補位字元不屬於 base64url 無補位格式
        VALID[:-1] + "+",
        VALID[:-1] + "/",
        VALID + "\n",
    ],
)
def test_invalid_challenge_is_rejected(value: str) -> None:
    with pytest.raises(InvalidCodeChallenge):
        CodeChallenge.parse(value)
