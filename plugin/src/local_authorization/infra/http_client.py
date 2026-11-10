"""本 context 對外 HTTP 呼叫共用的 client 設定（R4：所有對外呼叫都有 timeout）。"""

import httpx2

from local_authorization.domain.limits import HTTP_CONNECT_TIMEOUT_SECONDS, HTTP_READ_TIMEOUT_SECONDS


def new_http_client() -> httpx2.Client:
    # 寫入與從連線池取連線的逾時沿用讀取的值；真正需要分開的是「連不上」和「連上了但對方不回」
    return httpx2.Client(timeout=httpx2.Timeout(HTTP_READ_TIMEOUT_SECONDS, connect=HTTP_CONNECT_TIMEOUT_SECONDS))
