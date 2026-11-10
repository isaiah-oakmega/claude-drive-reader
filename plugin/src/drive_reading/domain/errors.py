"""Drive Reading 的 Failure。只描述發生了什麼；代碼、訊息與下一步由 mcp_server/failures.py 決定。"""


class DriveReadingError(Exception):
    """Drive Reading 的 Failure 的共同基底。"""


class NotFoundOrNoAccess(DriveReadingError):
    """Drive 回 404，或參數根本不是有效的 ID 或網址。

    Drive 對「沒有權限」也回 404，兩者無法區分（R6），所以訊息要同時提到兩種可能。
    """

    def __init__(self, reference: str) -> None:
        super().__init__(reference)
        self.reference = reference


class OutsideRoot(DriveReadingError):
    """目標不在 Root Folder 子樹內（R1）。"""

    def __init__(self, reference: str) -> None:
        super().__init__(reference)
        self.reference = reference


class GoogleApiError(DriveReadingError):
    """Drive 回了其他錯誤，或重試後仍然失敗（R7）。"""

    def __init__(self, status: int | None, reason: str) -> None:
        super().__init__(status, reason)
        # status 為 None 代表連線本身失敗，沒有拿到 HTTP 回應
        self.status = status
        self.reason = reason
