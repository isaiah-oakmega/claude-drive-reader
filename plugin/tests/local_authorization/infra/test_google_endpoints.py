"""本機直接呼叫的兩個 Google 端點：revoke（A6）與 Drive about.get（C2 的 current_account）。"""

from urllib.parse import parse_qs

import httpx2
import pytest

from local_authorization.domain.credential import RevokeOutcome
from local_authorization.infra.google_account import GoogleAccount
from local_authorization.infra.google_revoke import GoogleRevoker


def mock_client(respond) -> tuple[httpx2.Client, list[httpx2.Request]]:
    seen: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append(request)
        return respond(request)

    return httpx2.Client(transport=httpx2.MockTransport(handler)), seen


def raise_connect_error(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("offline")


# ---------- revoke ----------


def test_revoke_posts_token_as_form_to_google() -> None:
    http, seen = mock_client(lambda request: httpx2.Response(200))

    assert GoogleRevoker(http).revoke("1//R") is RevokeOutcome.REVOKED
    request = seen[0]
    assert (request.method, str(request.url)) == ("POST", "https://oauth2.googleapis.com/revoke")
    # token 放在 body，不放在網址：網址可能被 proxy 或 log 記下
    assert parse_qs(request.content.decode()) == {"token": ["1//R"]}


@pytest.mark.parametrize(
    "respond, expected",
    [
        (lambda request: httpx2.Response(400, json={"error": "invalid_token"}), RevokeOutcome.ALREADY_INVALID),
        (lambda request: httpx2.Response(503, text="down"), RevokeOutcome.FAILED),
        (raise_connect_error, RevokeOutcome.FAILED),
    ],
    ids=["already-invalid", "google-down", "offline"],
)
def test_revoke_outcomes(respond, expected: RevokeOutcome) -> None:
    http, _ = mock_client(respond)

    assert GoogleRevoker(http).revoke("1//R") is expected


# ---------- about.get ----------


def test_account_email_comes_from_drive_about() -> None:
    http, seen = mock_client(lambda request: httpx2.Response(200, json={"user": {"emailAddress": "someone@example.com"}}))

    assert GoogleAccount(http).email("ya29.A") == "someone@example.com"
    request = seen[0]
    assert str(request.url).startswith("https://www.googleapis.com/drive/v3/about?")
    assert request.url.params["fields"] == "user(emailAddress)"
    assert request.headers["authorization"] == "Bearer ya29.A"


@pytest.mark.parametrize(
    "respond",
    [
        lambda request: httpx2.Response(401, json={"error": {"code": 401}}),
        lambda request: httpx2.Response(200, json={"user": {}}),
        lambda request: httpx2.Response(200, text="not json"),
        raise_connect_error,
    ],
    ids=["401", "no-email", "not-json", "offline"],
)
def test_account_email_is_none_when_unavailable(respond) -> None:
    # email 只用來讓訊息更好懂（R6、auth_status），拿不到時不應該讓原本的操作失敗
    http, _ = mock_client(respond)

    assert GoogleAccount(http).email("ya29.A") is None
