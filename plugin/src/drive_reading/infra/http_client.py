"""Drive Reading 對外 HTTP 呼叫的 client 設定（R4：所有對外呼叫都有 timeout）。"""

import httpx2

from drive_reading.domain.limits import HTTP_CONNECT_TIMEOUT_SECONDS, HTTP_READ_TIMEOUT_SECONDS


def new_http_client() -> httpx2.Client:
    # 和 Local Authorization 各自建立：兩個 context 的逾時各自定義在自己的 limits.py
    return httpx2.Client(timeout=httpx2.Timeout(HTTP_READ_TIMEOUT_SECONDS, connect=HTTP_CONNECT_TIMEOUT_SECONDS))
