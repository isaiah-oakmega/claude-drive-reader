"""Google OAuth client：授權網址的組成、token 請求帶上 secret、各種上游回應的對應。全部用 MockTransport，不連網。"""

from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from token_broker.domain.code_relay import RelayState
from token_broker.domain.errors import UpstreamRejected, UpstreamUnavailable
from token_broker.domain.pkce import CodeChallenge
from token_broker.domain.token_grant import AuthorizationCodeGrant, RefreshTokenGrant
from token_broker.infra.google_oauth import GoogleOAuthClient

STATE = RelayState.parse("53682.Jq3vX8bT2mN5pR7sW9yZ1aC4dE6fG0hK2lM4nP6qR8s")
CHALLENGE = CodeChallenge.parse("E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM")
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
TOKEN_BODY = {
    "access_token": "ya29.access",
    "expires_in": 3599,
    "scope": "https://www.googleapis.com/auth/drive.readonly",
    "token_type": "Bearer",
    "refresh_token": "1//refresh",
    "id_token": "should-not-be-forwarded",
}


def make_client(handler) -> GoogleOAuthClient:
    return GoogleOAuthClient(
        client_id="client-123.apps.googleusercontent.com",
        client_secret="s3cr3t",
        redirect_uri="https://broker.example/callback",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def form_of(request: httpx.Request) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


def test_authorization_url_has_exactly_the_fixed_parameters() -> None:
    url = make_client(lambda r: httpx.Response(500)).authorization_url(STATE, CHALLENGE)

    parts = urlsplit(url)
    params = {k: v[0] for k, v in parse_qs(parts.query).items()}
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://accounts.google.com/o/oauth2/v2/auth"
    assert params == {
        "client_id": "client-123.apps.googleusercontent.com",
        "redirect_uri": "https://broker.example/callback",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/drive.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "code_challenge": CHALLENGE.value,
        "code_challenge_method": "S256",
        "state": STATE.value,
    }


def test_code_exchange_sends_secret_verifier_and_redirect_uri() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=TOKEN_BODY)

    make_client(handler).exchange(
        AuthorizationCodeGrant(grant_type="authorization_code", code="4/abc", code_verifier=VERIFIER)
    )

    assert str(seen[0].url) == "https://oauth2.googleapis.com/token"
    assert form_of(seen[0]) == {
        "grant_type": "authorization_code",
        "code": "4/abc",
        "code_verifier": VERIFIER,
        "client_id": "client-123.apps.googleusercontent.com",
        "client_secret": "s3cr3t",
        "redirect_uri": "https://broker.example/callback",
    }


def test_refresh_sends_secret_without_redirect_uri() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=TOKEN_BODY)

    make_client(handler).exchange(RefreshTokenGrant(grant_type="refresh_token", refresh_token="1//refresh"))

    assert form_of(seen[0]) == {
        "grant_type": "refresh_token",
        "refresh_token": "1//refresh",
        "client_id": "client-123.apps.googleusercontent.com",
        "client_secret": "s3cr3t",
    }


def test_success_keeps_only_contract_fields() -> None:
    issued = make_client(lambda r: httpx.Response(200, json=TOKEN_BODY)).exchange(
        RefreshTokenGrant(grant_type="refresh_token", refresh_token="1//refresh")
    )

    assert issued.model_dump(exclude_none=True) == {
        "access_token": "ya29.access",
        "expires_in": 3599,
        "scope": "https://www.googleapis.com/auth/drive.readonly",
        "token_type": "Bearer",
        "refresh_token": "1//refresh",
    }


def test_google_oauth_error_is_passed_through() -> None:
    body = {"error": "invalid_grant", "error_description": "Token has been expired or revoked."}
    client = make_client(lambda r: httpx.Response(400, json=body))

    with pytest.raises(UpstreamRejected) as excinfo:
        client.exchange(RefreshTokenGrant(grant_type="refresh_token", refresh_token="1//refresh"))

    assert excinfo.value.error == "invalid_grant"
    assert excinfo.value.error_description == "Token has been expired or revoked."


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={"error": "internal"}),
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(429, json={"error": "rate_limited"}),
        httpx.Response(400, text="<html>not json</html>"),
        httpx.Response(200, json={"unexpected": "shape"}),
    ],
    ids=["500", "503", "429", "400-not-json", "200-bad-shape"],
)
def test_unusable_upstream_responses_become_unavailable(response: httpx.Response) -> None:
    client = make_client(lambda r: response)

    with pytest.raises(UpstreamUnavailable):
        client.exchange(RefreshTokenGrant(grant_type="refresh_token", refresh_token="1//refresh"))


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectError("refused"), httpx.ReadTimeout("slow")],
    ids=["connect-error", "read-timeout"],
)
def test_network_failures_become_unavailable(error: httpx.HTTPError) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    with pytest.raises(UpstreamUnavailable):
        make_client(handler).exchange(RefreshTokenGrant(grant_type="refresh_token", refresh_token="1//refresh"))
