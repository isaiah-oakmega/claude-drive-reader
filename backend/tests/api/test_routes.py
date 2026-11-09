"""C1：Token Broker HTTP API 的合約測試，加上 B1（log 不含機密）與 B6（錯誤頁不回顯參數）。"""

import logging
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

STATE = "53682.Jq3vX8bT2mN5pR7sW9yZ1aC4dE6fG0hK2lM4nP6qR8s"
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
TOKEN_BODY = {
    "access_token": "ya29.ACCESS-SECRET",
    "expires_in": 3599,
    "scope": "https://www.googleapis.com/auth/drive.readonly",
    "token_type": "Bearer",
    "refresh_token": "1//REFRESH-SECRET",
}


def query_of(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


# ---------- GET /authorize ----------


def test_authorize_redirects_to_google_with_fixed_parameters(client: TestClient) -> None:
    response = client.get("/authorize", params={"state": STATE, "code_challenge": CHALLENGE})

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert query_of(location) == {
        "client_id": "client-123.apps.googleusercontent.com",
        "redirect_uri": "https://broker.example/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "state": STATE,
    }


def test_authorize_ignores_scope_supplied_by_caller(client: TestClient) -> None:
    response = client.get(
        "/authorize",
        params={"state": STATE, "code_challenge": CHALLENGE, "scope": "https://www.googleapis.com/auth/drive"},
    )

    assert query_of(response.headers["location"])["scope"] == "https://www.googleapis.com/auth/drive.readonly"


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"state": STATE},
        {"code_challenge": CHALLENGE},
        {"state": "not-a-state", "code_challenge": CHALLENGE},
        {"state": STATE, "code_challenge": "plain-verifier"},
    ],
    ids=["none", "no-challenge", "no-state", "bad-state", "bad-challenge"],
)
def test_authorize_rejects_bad_requests_with_error_page(client: TestClient, params: dict) -> None:
    response = client.get("/authorize", params=params)

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("text/html")


# ---------- GET /callback ----------


def test_callback_relays_code_to_loopback(client: TestClient) -> None:
    response = client.get("/callback", params={"code": "4/CODE", "state": STATE, "scope": "x", "authuser": "0"})

    assert response.status_code == 302
    location = response.headers["location"]
    assert location.startswith("http://127.0.0.1:53682/callback?")
    # 只轉交本機需要的參數；Google 附帶的 scope、authuser 不轉交
    assert query_of(location) == {"code": "4/CODE", "state": STATE}


def test_callback_relays_user_denial_to_loopback(client: TestClient) -> None:
    response = client.get("/callback", params={"error": "access_denied", "state": STATE})

    assert response.status_code == 302
    assert query_of(response.headers["location"]) == {"error": "access_denied", "state": STATE}


@pytest.mark.parametrize(
    "state",
    ["", "53682", "80.Jq3vX8bT2mN5pR7sW9yZ1aC4dE6fG0hK2lM4nP6qR8s", "evil.example:53682.abcdefghijklmnop"],
    ids=["empty", "no-nonce", "low-port", "host-prefix"],
)
def test_callback_with_bad_state_never_redirects(client: TestClient, state: str) -> None:
    response = client.get("/callback", params={"code": "4/CODE", "state": state})

    assert response.status_code == 400
    assert "location" not in response.headers


# ---------- POST /token ----------


def test_token_exchange_returns_contract_fields(client: TestClient, google) -> None:
    google.respond = lambda request: httpx.Response(200, json=TOKEN_BODY | {"id_token": "x"})

    response = client.post(
        "/token", json={"grant_type": "authorization_code", "code": "4/CODE", "code_verifier": VERIFIER}
    )

    assert response.status_code == 200
    assert response.json() == TOKEN_BODY
    # RFC 6749 §5.1：token 回應不可被任何中間層快取
    assert response.headers["cache-control"] == "no-store"
    assert len(google.requests) == 1


def test_refresh_returns_contract_fields(client: TestClient, google) -> None:
    body = {k: v for k, v in TOKEN_BODY.items() if k != "refresh_token"}
    google.respond = lambda request: httpx.Response(200, json=body)

    response = client.post("/token", json={"grant_type": "refresh_token", "refresh_token": "1//REFRESH-SECRET"})

    assert response.status_code == 200
    assert response.json() == body


def test_google_rejection_is_passed_through_as_400(client: TestClient, google) -> None:
    google.respond = lambda request: httpx.Response(
        400, json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."}
    )

    response = client.post("/token", json={"grant_type": "refresh_token", "refresh_token": "1//REFRESH-SECRET"})

    assert response.status_code == 400
    assert response.json() == {"error": "invalid_grant", "error_description": "Token has been expired or revoked."}


def test_google_unavailable_becomes_502(client: TestClient, google) -> None:
    google.respond = lambda request: httpx.Response(503, text="down")

    response = client.post("/token", json={"grant_type": "refresh_token", "refresh_token": "1//REFRESH-SECRET"})

    assert response.status_code == 502
    assert response.json() == {"error": "upstream_unavailable"}


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"grant_type": "client_credentials"},
        {"grant_type": "refresh_token", "refresh_token": "1//x", "scope": "https://www.googleapis.com/auth/drive"},
        {"grant_type": "authorization_code", "code": "4/CODE"},
    ],
    ids=["empty", "unknown-grant", "extra-scope", "missing-verifier"],
)
def test_other_token_shapes_get_422_and_never_reach_google(client: TestClient, google, body: dict) -> None:
    response = client.post("/token", json=body)

    assert response.status_code == 422
    assert google.requests == []


# ---------- 靜態頁與健康檢查 ----------


def test_home_and_privacy_pages_are_served(client: TestClient) -> None:
    home = client.get("/")
    privacy = client.get("/privacy")

    assert home.status_code == 200 and home.headers["content-type"].startswith("text/html")
    assert privacy.status_code == 200 and privacy.headers["content-type"].startswith("text/html")
    assert "Drive Reader" in home.text
    assert "drive.readonly" in privacy.text


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.text == "ok"


@pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
def test_generated_api_docs_are_disabled(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 404


# ---------- B6：錯誤頁不回顯任何請求參數 ----------


@pytest.mark.parametrize(
    "path, params",
    [
        ("/authorize", {"state": "<script>alert(1)</script>", "code_challenge": CHALLENGE}),
        ("/authorize", {"state": STATE, "code_challenge": "<img src=x onerror=alert(1)>"}),
        ("/callback", {"state": "<script>alert(1)</script>", "error": "<b>boom</b>"}),
    ],
)
def test_error_pages_do_not_reflect_input(client: TestClient, path: str, params: dict) -> None:
    response = client.get(path, params=params)

    assert response.status_code == 400
    for value in params.values():
        assert value not in response.text
    assert "alert(1)" not in response.text


# ---------- B1：應用程式 log 不含 code、token、secret、query string ----------


def test_logs_contain_only_method_path_and_status(
    client: TestClient, google, caplog: pytest.LogCaptureFixture
) -> None:
    google.respond = lambda request: httpx.Response(200, json=TOKEN_BODY)
    caplog.set_level(logging.DEBUG)

    client.get("/callback", params={"code": "4/CODE-SECRET", "state": STATE})
    client.post("/token", json={"grant_type": "refresh_token", "refresh_token": "1//REFRESH-SECRET"})
    client.post("/token", json={"grant_type": "authorization_code", "code": "4/CODE-SECRET", "code_verifier": VERIFIER})

    text = caplog.text
    for secret in ["CODE-SECRET", "REFRESH-SECRET", "ACCESS-SECRET", "s3cr3t-never-logged", VERIFIER, "?"]:
        assert secret not in text
    assert "GET /callback 302" in text
    assert "POST /token 200" in text
