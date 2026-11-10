"""app 層測試用的假 infra。只模擬 app 依賴的行為，不重測 infra 本身（infra 有自己的測試）。"""

from collections.abc import Callable
from pathlib import Path

from local_authorization.domain.attempt import AttemptResult
from local_authorization.domain.credential import IssuedTokens, LocalCredential, RevokeOutcome

SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def issued(access: str = "ya29.A", refresh: str | None = None, expires_in: int = 3600) -> IssuedTokens:
    return IssuedTokens(access_token=access, expires_in=expires_in, scope=SCOPE, refresh_token=refresh)


def raises(error: Exception) -> Callable[[], IssuedTokens]:
    """給 FakeBroker 的 *_answer 用：被呼叫時拋出指定的例外。"""

    def answer() -> IssuedTokens:
        raise error

    return answer


def credential(refresh: str = "1//R") -> LocalCredential:
    return LocalCredential(refresh_token=refresh, scope=SCOPE, obtained_at="2026-11-10T00:00:00+00:00")


class Clock:
    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


class FakeStore:
    def __init__(self, initial: LocalCredential | None = None) -> None:
        self.credential = initial
        self.saves: list[LocalCredential] = []
        self.path = Path("/home/someone/.config/claude-drive-reader/credentials.json")
        self.permissions_enforced = True

    def load(self) -> LocalCredential | None:
        return self.credential

    def save(self, credential: LocalCredential) -> None:
        self.saves.append(credential)
        self.credential = credential

    def delete(self) -> bool:
        existed = self.credential is not None
        self.credential = None
        return existed


class FakeBroker:
    base_url = "https://broker.example"

    def __init__(self) -> None:
        self.refreshes: list[str] = []
        self.exchanges: list[tuple[str, str]] = []
        self.refresh_answer: Callable[[], IssuedTokens] = lambda: issued(access=f"ya29.{len(self.refreshes)}")
        self.exchange_answer: Callable[[], IssuedTokens] = lambda: issued(access="ya29.NEW", refresh="1//NEW")

    def authorization_url(self, state: str, code_challenge: str) -> str:
        return f"{self.base_url}/authorize?state={state}&code_challenge={code_challenge}"

    def refresh(self, refresh_token: str) -> IssuedTokens:
        self.refreshes.append(refresh_token)
        return self.refresh_answer()

    def exchange_code(self, code: str, code_verifier: str) -> IssuedTokens:
        self.exchanges.append((code, code_verifier))
        return self.exchange_answer()


class FakeAccount:
    def __init__(self, email: str | None = "someone@example.com") -> None:
        self.address = email
        self.lookups: list[str] = []

    def email(self, access_token: str) -> str | None:
        self.lookups.append(access_token)
        return self.address


class FakeRevoker:
    def __init__(self, outcome: RevokeOutcome = RevokeOutcome.REVOKED) -> None:
        self.outcome = outcome
        self.revoked: list[str] = []

    def revoke(self, token: str) -> RevokeOutcome:
        self.revoked.append(token)
        return self.outcome


class FakeListener:
    def __init__(self, port: int) -> None:
        self.port = port
        self.closed = False
        self.handle: Callable[[dict[str, str]], AttemptResult | None] | None = None
        self.timeout_seconds: float | None = None
        self.on_timeout: Callable[[], None] | None = None

    def serve(self, handle, timeout_seconds: float, on_timeout) -> None:
        self.handle, self.timeout_seconds, self.on_timeout = handle, timeout_seconds, on_timeout

    def close(self) -> None:
        self.closed = True

    # 模擬瀏覽器打到 /callback
    def callback(self, **params: str) -> AttemptResult | None:
        assert self.handle is not None and not self.closed
        return self.handle(params)


class FakeListen:
    """取代 LoopbackListener.bind：記錄每次 bind 的 port，回傳可以手動觸發 callback 的假 listener。"""

    def __init__(self, assigned_port: int = 53682) -> None:
        self.assigned_port = assigned_port
        self.requested_ports: list[int | None] = []
        self.listeners: list[FakeListener] = []
        self.error: OSError | None = None

    def __call__(self, port: int | None) -> FakeListener:
        self.requested_ports.append(port)
        if self.error is not None:
            raise self.error
        self.listeners.append(FakeListener(port or self.assigned_port))
        return self.listeners[-1]
