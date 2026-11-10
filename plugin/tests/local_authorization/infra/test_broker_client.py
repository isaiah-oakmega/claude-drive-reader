"""C1 的消費端：本機送出的請求形狀，以及 Broker 各種回應對應到的結果與例外。"""

import json
from urllib.parse import parse_qs, urlsplit

import httpx2
import pytest

from local_authorization.domain.credential import IssuedTokens
from local_authorization.domain.errors import AuthExpired, BrokerUnreachable
from local_authorization.infra.broker_client import BrokerClient

BROKER = "https://broker.example"
SCOPE = "https://www.googleapis.com/auth/drive.readonly"
TOKEN_BODY = {"access_token": "ya29.A", "expires_in": 3599, "scope": SCOPE, "token_type": "Bearer", "refresh_token": "1//R"}


class FakeBroker:
    def __init__(self) -> None:
        self.requests: list[httpx2.Request] = []
        self.respond = lambda request: httpx2.Response(200, json=TOKEN_BODY)

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return self.respond(request)


@pytest.fixture
def broker() -> FakeBroker:
    return FakeBroker()


@pytest.fixture
def client(broker: FakeBroker) -> BrokerClient:
    return BrokerClient(BROKER, httpx2.Client(transport=httpx2.MockTransport(broker.handler)))


# ---------- 請求形狀 ----------


@pytest.mark.parametrize("base", [BROKER, BROKER + "/"])
def test_authorization_url_points_at_broker_authorize(base: str) -> None:
    client = BrokerClient(base, httpx2.Client())

    url = client.authorization_url(state="53682.abcdefghijklmnop", code_challenge="C" * 43)

    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://broker.example/authorize"
    # 只送這兩個參數；scope、client_id 等由 Broker 補上（B4、B5）
    assert parse_qs(parts.query) == {"state": ["53682.abcdefghijklmnop"], "code_challenge": ["C" * 43]}


def test_exchange_code_posts_authorization_code_grant(client: BrokerClient, broker: FakeBroker) -> None:
    issued = client.exchange_code(code="4/CODE", code_verifier="V" * 64)

    request = broker.requests[0]
    assert (request.method, str(request.url)) == ("POST", "https://broker.example/token")
    assert json.loads(request.content) == {"grant_type": "authorization_code", "code": "4/CODE", "code_verifier": "V" * 64}
    assert issued == IssuedTokens(access_token="ya29.A", expires_in=3599, scope=SCOPE, refresh_token="1//R")


def test_refresh_posts_refresh_token_grant(client: BrokerClient, broker: FakeBroker) -> None:
    broker.respond = lambda request: httpx2.Response(200, json={k: v for k, v in TOKEN_BODY.items() if k != "refresh_token"})

    issued = client.refresh("1//R")

    assert json.loads(broker.requests[0].content) == {"grant_type": "refresh_token", "refresh_token": "1//R"}
    assert issued.refresh_token is None


# ---------- 失敗的對應 ----------


def test_invalid_grant_means_auth_expired(client: BrokerClient, broker: FakeBroker) -> None:
    broker.respond = lambda request: httpx2.Response(400, json={"error": "invalid_grant", "error_description": "Token has been expired or revoked."})

    with pytest.raises(AuthExpired):
        client.refresh("1//R")
    with pytest.raises(AuthExpired):
        client.exchange_code(code="4/USED", code_verifier="V" * 64)


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(400, json={"error": "invalid_client", "error_description": "Unauthorized"}),
        httpx2.Response(400, text="not json"),
        httpx2.Response(422, json={"detail": []}),
        httpx2.Response(502, json={"error": "upstream_unavailable"}),
        httpx2.Response(503, text="Service Unavailable"),
        httpx2.Response(404, text="Not Found"),
        httpx2.Response(200, text="<html>captive portal</html>"),
        httpx2.Response(200, json={"access_token": "ya29.A"}),
        httpx2.Response(200, json=TOKEN_BODY | {"expires_in": "3599"}),
        httpx2.Response(200, json=TOKEN_BODY | {"expires_in": 0}),
        httpx2.Response(200, json=TOKEN_BODY | {"access_token": ""}),
    ],
    ids=[
        "400-other-error",
        "400-not-json",
        "422",
        "502",
        "503",
        "404-wrong-url",
        "200-not-json",
        "200-missing-fields",
        "200-string-expiry",
        "200-zero-expiry",
        "200-empty-token",
    ],
)
def test_unusable_responses_mean_broker_unreachable(client: BrokerClient, broker: FakeBroker, response: httpx2.Response) -> None:
    broker.respond = lambda request: response

    with pytest.raises(BrokerUnreachable) as raised:
        client.refresh("1//R")
    assert raised.value.broker_url == BROKER


@pytest.mark.parametrize("error", [httpx2.ConnectError("refused"), httpx2.ReadTimeout("slow")], ids=["connect", "timeout"])
def test_network_failures_mean_broker_unreachable(client: BrokerClient, broker: FakeBroker, error: Exception) -> None:
    def fail(request: httpx2.Request) -> httpx2.Response:
        raise error

    broker.respond = fail

    with pytest.raises(BrokerUnreachable):
        client.exchange_code(code="4/CODE", code_verifier="V" * 64)


def test_code_exchange_is_not_retried(client: BrokerClient, broker: FakeBroker) -> None:
    # auth code 只能用一次，重送只會拿到 invalid_grant（實作規格「冪等性」）
    broker.respond = lambda request: httpx2.Response(503, text="down")

    with pytest.raises(BrokerUnreachable):
        client.exchange_code(code="4/CODE", code_verifier="V" * 64)
    assert len(broker.requests) == 1
