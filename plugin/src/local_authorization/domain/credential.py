"""Local Credential（A3）與記憶體中的 access token。"""

from dataclasses import dataclass
from enum import StrEnum

from local_authorization.domain.limits import REFRESH_MARGIN_SECONDS


@dataclass(frozen=True)
class LocalCredential:
    """寫進檔案的唯一內容。access token 不在這裡：它一小時就過期，存檔只會多一份可被偷走的東西。"""

    refresh_token: str
    scope: str
    # ISO 8601（UTC），只供人查看與除錯，程式不依它判斷任何事
    obtained_at: str


@dataclass(frozen=True)
class IssuedTokens:
    """Broker /token 的成功回應（C1）。refresh_token 只在換 code 時一定有；refresh 時 Google 不一定附。"""

    access_token: str
    expires_in: int
    scope: str
    refresh_token: str | None = None


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_at: float

    @classmethod
    def issued(cls, value: str, expires_in: int, now: float) -> "AccessToken":
        return cls(value=value, expires_at=now + expires_in)

    def is_fresh(self, now: float) -> bool:
        return now < self.expires_at - REFRESH_MARGIN_SECONDS


class RevokeOutcome(StrEnum):
    """logout 時向 Google revoke 的結果（A6）。"""

    REVOKED = "revoked"
    # Google 回報 token 本來就無效（例如使用者已在帳號頁撤銷），結果等同撤銷成功
    ALREADY_INVALID = "already_invalid"
    FAILED = "failed"
