"""Local Authorization 的 Failure（C2 的例外）。只描述發生了什麼；代碼、訊息與下一步由 mcp_server/failures.py 決定。"""


class AuthorizationError(Exception):
    """C2 會拋出的例外的共同基底，讓呼叫端可以一次攔下「拿不到 token」的所有情況。"""


class NotAuthorized(AuthorizationError):
    """沒有 Local Credential：從未授權，或已經 logout。"""


class AuthExpired(AuthorizationError):
    """Google 回 invalid_grant：refresh token 已被撤銷或過期，Local Credential 已刪除（A5）。"""


class BrokerUnreachable(AuthorizationError):
    """Broker 無法提供 token：連不上、逾時、5xx，或回應不是 C1 的形狀。"""

    def __init__(self, broker_url: str) -> None:
        super().__init__(broker_url)
        # 附上網址，讓使用者能判斷是網路問題還是 DRIVE_READER_BROKER_URL 設錯（情境 14）
        self.broker_url = broker_url
