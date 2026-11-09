"""組裝層：建立 infra 物件並接上 api。Cloud Run 透過 `uvicorn --factory` 呼叫 create_app_from_env。"""

import logging
import os

import httpx
from fastapi import FastAPI, Request, Response

from token_broker.api.routes import build_router
from token_broker.domain.limits import HTTP_CONNECT_TIMEOUT_SECONDS, HTTP_READ_TIMEOUT_SECONDS
from token_broker.infra.google_oauth import GoogleOAuthClient
from token_broker.settings import Settings

logger = logging.getLogger("token_broker")


def create_app(settings: Settings, http: httpx.Client) -> FastAPI:
    # B1：httpx 在 INFO 等級會記下每個請求的完整網址（含 query string）。
    # 調到 WARNING，應用程式的 log 就只剩下面 middleware 那一行。
    logging.getLogger("httpx").setLevel(logging.WARNING)

    oauth = GoogleOAuthClient(
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        redirect_uri=settings.redirect_uri,
        http=http,
    )
    # 關閉自動產生的 API 文件：Broker 不是公開 API，不需要對外描述端點與欄位
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.include_router(build_router(oauth))

    @app.middleware("http")
    async def log_request(request: Request, call_next) -> Response:
        response = await call_next(request)
        # B1：只記方法、路徑、狀態碼。query string 可能帶 auth code，request body 可能帶 token，
        # 所以用 url.path（不含 query），也從不讀取 body。uvicorn 自己的 access log 在啟動時關閉。
        logger.info("%s %s %s", request.method, request.url.path, response.status_code)
        return response

    return app


def create_app_from_env() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = Settings.from_env(os.environ)
    # 逾時：連線 10 秒、讀取 30 秒（實作規格「參數值」）
    http = httpx.Client(timeout=httpx.Timeout(HTTP_READ_TIMEOUT_SECONDS, connect=HTTP_CONNECT_TIMEOUT_SECONDS))
    return create_app(settings, http)
