"""api 測試共用的組裝：用 MockTransport 取代 Google，組出完整的 FastAPI app。"""

from collections.abc import Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from token_broker.main import create_app
from token_broker.settings import Settings

SETTINGS = Settings(
    client_id="client-123.apps.googleusercontent.com",
    client_secret="s3cr3t-never-logged",
    public_base_url="https://broker.example",
)

GoogleHandler = Callable[[httpx.Request], httpx.Response]


class FakeGoogle:
    """記錄 Broker 送給 Google 的請求，並回傳測試指定的回應。"""

    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.respond: GoogleHandler = lambda request: httpx.Response(500)

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.respond(request)


@pytest.fixture
def google() -> FakeGoogle:
    return FakeGoogle()


@pytest.fixture
def client(google: FakeGoogle) -> TestClient:
    http = httpx.Client(transport=httpx.MockTransport(google.handle))
    # follow_redirects=False：要檢查的是 Broker 回的 302 本身，而不是跟著轉過去
    return TestClient(create_app(SETTINGS, http), follow_redirects=False)
