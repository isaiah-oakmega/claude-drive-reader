"""C1：Token Broker 的 HTTP 端點。只負責把 HTTP 轉成 use case 呼叫，再把結果或領域例外轉成 HTTP 回應。"""

from typing import Annotated

from fastapi import APIRouter, Body, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from token_broker.api import pages
from token_broker.app.authorize import build_authorization_redirect
from token_broker.app.exchange_token import exchange_token
from token_broker.app.relay_callback import build_relay_redirect
from token_broker.domain.errors import (
    InvalidCodeChallenge,
    InvalidState,
    UpstreamRejected,
    UpstreamUnavailable,
)
from token_broker.domain.token_grant import AuthorizationCodeGrant, RefreshTokenGrant
from token_broker.infra.google_oauth import GoogleOAuthClient

# RFC 6749 §5.1：含 token 的回應必須禁止快取，否則可能被瀏覽器或中間的 proxy 存下來
_NO_STORE = {"Cache-Control": "no-store"}


def build_router(oauth: GoogleOAuthClient) -> APIRouter:
    # 依賴透過閉包傳入，而不是 FastAPI 的 Depends：route 用到什麼，在這個函式裡一眼就看得到
    router = APIRouter()

    # 回傳型別標成 Response：FastAPI 會直接送出，不會嘗試從型別產生 response model
    @router.get("/authorize")
    def authorize(state: str = "", code_challenge: str = "") -> Response:
        try:
            url = build_authorization_redirect(oauth, state, code_challenge)
        except (InvalidState, InvalidCodeChallenge):
            return HTMLResponse(pages.error_page(pages.ErrorKind.INVALID_AUTHORIZE_REQUEST), status_code=400)
        return RedirectResponse(url, status_code=302)

    @router.get("/callback")
    def callback(request: Request) -> Response:
        try:
            url = build_relay_redirect(request.query_params)
        except InvalidState:
            # 不轉址：state 不合法時，我們無法確定該轉到哪裡，也不能讓它變成 open redirect（B2）
            return HTMLResponse(pages.error_page(pages.ErrorKind.INVALID_CALLBACK), status_code=400)
        return RedirectResponse(url, status_code=302)

    @router.post("/token")
    def token(
        # discriminator 讓 FastAPI 依 grant_type 選擇要套用的形狀；不符合任何一種就自動回 422（B3）
        grant: Annotated[AuthorizationCodeGrant | RefreshTokenGrant, Body(discriminator="grant_type")],
    ) -> JSONResponse:
        try:
            issued = exchange_token(oauth, grant)
        except UpstreamRejected as rejected:
            # 原樣轉交 Google 的錯誤，本機據此判斷例如 invalid_grant 要刪除 Local Credential（A5）
            body = {"error": rejected.error, "error_description": rejected.error_description}
            return JSONResponse(body, status_code=400, headers=_NO_STORE)
        except UpstreamUnavailable:
            return JSONResponse({"error": "upstream_unavailable"}, status_code=502, headers=_NO_STORE)
        return JSONResponse(issued.model_dump(exclude_none=True), headers=_NO_STORE)

    @router.get("/")
    def home() -> HTMLResponse:
        return HTMLResponse(pages.home_page())

    @router.get("/privacy")
    def privacy() -> HTMLResponse:
        return HTMLResponse(pages.privacy_page())

    # 不用慣例的 /healthz：Cloud Run 保留結尾是 z 的路徑，請求到不了容器。
    @router.get("/health")
    def health() -> PlainTextResponse:
        return PlainTextResponse("ok")

    return router
