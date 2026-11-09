"""PKCE code_challenge 的格式規則。"""

import re
from dataclasses import dataclass

from token_broker.domain.errors import InvalidCodeChallenge

# S256 的 challenge 是 SHA-256（32 bytes）的 base64url 無補位編碼，長度固定 43（RFC 7636 §4.2）。
# 只接受 S256：plain 方法等於直接把 verifier 放在網址上，失去 PKCE 的保護。
_S256_CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43}", re.ASCII)


@dataclass(frozen=True)
class CodeChallenge:
    value: str

    @classmethod
    def parse(cls, value: str) -> "CodeChallenge":
        if _S256_CHALLENGE.fullmatch(value) is None:
            raise InvalidCodeChallenge
        return cls(value=value)
