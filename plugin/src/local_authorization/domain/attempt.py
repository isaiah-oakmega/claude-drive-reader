"""Authorization Attempt（A1、A2）：一次進行中的授權嘗試，短效、一次性。

這裡只有規則，不碰網路與檔案：誰的 callback 算數、什麼時候結束、結果是什麼。
時間以呼叫端傳入的 `now`（time.monotonic 的秒數）表示，測試可以直接給數字。
"""

import base64
import hashlib
import hmac
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from local_authorization.domain.limits import ATTEMPT_TTL_SECONDS
from local_authorization.domain.relay_state import new_relay_state


class AttemptResult(StrEnum):
    SUCCEEDED = "succeeded"
    DENIED = "denied"
    TIMED_OUT = "timed_out"
    FAILED = "failed"


@dataclass(frozen=True)
class CodeReceived:
    """state 驗證通過且帶著 code：接下來要拿 code 加 verifier 去 Broker 換 token。"""

    code: str


@dataclass(frozen=True)
class Pkce:
    verifier: str
    challenge: str

    @classmethod
    def generate(cls) -> "Pkce":
        # 48 bytes 隨機值 → 64 個 base64url 字元，落在 RFC 7636 要求的 43–128 之間
        verifier = secrets.token_urlsafe(48)
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        # S256：challenge = BASE64URL(SHA256(verifier))，去掉補位的 "="
        challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return cls(verifier=verifier, challenge=challenge)


@dataclass
class AuthorizationAttempt:
    port: int
    state: str
    pkce: Pkce
    expires_at: float
    result: AttemptResult | None = None
    # 收到有效的 code 之後就不再接受任何 callback，即使換 token 還沒完成
    _code_received: bool = field(default=False, init=False, repr=False)

    @classmethod
    def start(cls, port: int, now: float) -> "AuthorizationAttempt":
        return cls(port=port, state=new_relay_state(port), pkce=Pkce.generate(), expires_at=now + ATTEMPT_TTL_SECONDS)

    def is_pending(self, now: float) -> bool:
        return self.result is None and not self._code_received and now < self.expires_at

    def seconds_left(self, now: float) -> float:
        return max(0.0, self.expires_at - now)

    def receive_callback(self, params: Mapping[str, str], now: float) -> CodeReceived | AttemptResult | None:
        """回傳 None 代表「不算數」：呼叫端回 400，listener 繼續等（A2）。"""
        if self.result is None and not self._code_received and now >= self.expires_at:
            self.result = AttemptResult.TIMED_OUT
        if not self.is_pending(now) or not self._state_matches(params.get("state", "")):
            return None

        # state 正確之後才看內容。只有這兩種情況會結束 Attempt
        if "error" in params:
            # access_denied 是使用者按了「取消」；其他 error 是 Google 端的問題
            self.result = AttemptResult.DENIED if params["error"] == "access_denied" else AttemptResult.FAILED
            return self.result
        if params.get("code"):
            self._code_received = True
            return CodeReceived(code=params["code"])
        return None

    def finish_exchange(self, ok: bool) -> None:
        self.result = AttemptResult.SUCCEEDED if ok else AttemptResult.FAILED

    def expire(self) -> None:
        # 只有還在等的 Attempt 會變成逾時；已經有結果的保留原本的結果
        if self.result is None and not self._code_received:
            self.result = AttemptResult.TIMED_OUT

    def _state_matches(self, received: str) -> bool:
        # 常數時間比對，不讓回應時間洩漏 nonce 對了幾個字元（A2）。
        # 先轉成 bytes：compare_digest 遇到非 ASCII 的 str 會拋例外，而 state 來自任意的請求。
        return hmac.compare_digest(received.encode("utf-8"), self.state.encode("utf-8"))
