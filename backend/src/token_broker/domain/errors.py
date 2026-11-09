"""Token Broker 的領域例外：只描述發生了什麼，由 api 層決定回應的 HTTP 狀態與頁面。"""


class InvalidState(ValueError):
    """state 不符合 <port>.<nonce> 格式，或 port 超出允許範圍（B2）。"""


class InvalidCodeChallenge(ValueError):
    """code_challenge 不是 S256 格式。"""


class UpstreamRejected(Exception):
    """Google 拒絕了 token 請求，例如 invalid_grant。內容原樣轉交給本機（C1 的 400）。"""

    def __init__(self, error: str, error_description: str | None) -> None:
        super().__init__(error)
        self.error = error
        self.error_description = error_description


class UpstreamUnavailable(Exception):
    """連不到 Google，或 Google 回了無法解讀的回應（C1 的 502）。"""
