"""把真的 listener、credential 檔、Broker client 接起來跑一次授權，只有 Broker 的 HTTP 是假的。

app 與 infra 各自都有測試；這裡只確認它們接在一起時，thread 與真實的 HTTP 請求能走完整條流程。
"""

import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest

from local_authorization.app import AccessTokenProvider, AttemptResult, AuthorizationService
from local_authorization.infra.broker_client import BrokerClient
from local_authorization.infra.credential_store import CredentialStore
from local_authorization.infra.google_account import GoogleAccount
from local_authorization.infra.google_revoke import GoogleRevoker

SCOPE = "https://www.googleapis.com/auth/drive.readonly"


def fake_google_side(request: httpx2.Request) -> httpx2.Response:
    if request.url.path == "/token":
        body = json.loads(request.content)
        assert body["grant_type"] == "authorization_code"
        return httpx2.Response(200, json={"access_token": "ya29.A", "expires_in": 3599, "scope": SCOPE, "token_type": "Bearer", "refresh_token": "1//R"})
    if request.url.path == "/drive/v3/about":
        return httpx2.Response(200, json={"user": {"emailAddress": "someone@example.com"}})
    return httpx2.Response(404)


@pytest.fixture
def service(tmp_path: Path):
    http = httpx2.Client(transport=httpx2.MockTransport(fake_google_side))
    store = CredentialStore(tmp_path / "credentials.json")
    broker = BrokerClient("https://broker.example", http)
    tokens = AccessTokenProvider(store=store, broker=broker, account=GoogleAccount(http))
    service = AuthorizationService(
        broker=broker,
        store=store,
        tokens=tokens,
        revoker=GoogleRevoker(http),
        open_browser=lambda url: False,
        callback_port=None,
    )
    # 授權完成後 listener 會自己關閉；測試中途失敗時，它的 thread 與計時器都是 daemon，不會卡住測試
    return service, store


def browser_returns(state: str, **params: str) -> httpx2.Response:
    port = state.split(".")[0]
    with httpx2.Client(trust_env=False, timeout=5) as client:
        return client.get(f"http://127.0.0.1:{port}/callback", params={"state": state, **params})


def test_full_authorization_over_real_listener(service) -> None:
    service, store = service
    started = service.authorize()
    state = parse_qs(urlsplit(started.url).query)["state"][0]

    port = state.split(".")[0]
    noise = browser_returns(f"{port}.not-the-right-nonce-at-all", code="4/X")
    page = browser_returns(state, code="4/CODE")

    assert noise.status_code == 400
    assert page.status_code == 200 and "授權完成" in page.text
    assert store.load().refresh_token == "1//R"
    status = service.status()
    assert (status.authorized, status.account, status.last_result) == (True, "someone@example.com", AttemptResult.SUCCEEDED)
    if sys.platform != "win32":
        assert (store.path.stat().st_mode & 0o777) == 0o600
