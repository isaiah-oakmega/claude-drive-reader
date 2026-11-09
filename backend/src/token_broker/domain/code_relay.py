"""Code Relay（B2）：從 state 取出本機 port，產生唯一允許的轉址目標。"""

import re
from dataclasses import dataclass

from token_broker.domain.errors import InvalidState

MIN_PORT = 1024
MAX_PORT = 65535

# state = "<port>.<nonce>"。
# - port：不允許前導零，同一個 port 只有一種寫法，也避免 "01024" 這類邊界寫法繞過檢查。
# - nonce：本機產生的 base64url 字串。Broker 不比對 nonce（那是本機的責任），
#   只限制字元集與長度，確保 state 原樣帶回網址時不會夾帶 host、路徑或標記。
# re.ASCII 讓 [0-9] 與 \w 之類的規則只認 ASCII，全形數字不會被當成 port。
_STATE_PATTERN = re.compile(r"([1-9][0-9]{3,4})\.([A-Za-z0-9_-]{16,128})", re.ASCII)


@dataclass(frozen=True)
class RelayState:
    port: int
    value: str

    @classmethod
    def parse(cls, state: str) -> "RelayState":
        # fullmatch 而不是 match：結尾的換行或多餘字元都要算不合法
        match = _STATE_PATTERN.fullmatch(state)
        if match is None:
            raise InvalidState
        port = int(match.group(1))
        if not MIN_PORT <= port <= MAX_PORT:
            raise InvalidState
        return cls(port=port, value=state)

    def loopback_callback_url(self) -> str:
        # host 寫死成 127.0.0.1：不論 state 寫了什麼，轉址都不可能離開使用者本機，
        # 所以 Broker 不會變成 open redirect。
        return f"http://127.0.0.1:{self.port}/callback"
