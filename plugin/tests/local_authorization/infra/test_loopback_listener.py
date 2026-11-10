"""A2 與 A7 的本機 listener：真的在 127.0.0.1 開 port，用 HTTP client 打它。"""

import socket
import threading

import httpx2
import pytest

from local_authorization.domain.attempt import AttemptResult
from local_authorization.infra.loopback_listener import LoopbackListener

INJECTION = "<script>alert(1)</script>"


def get(port: int, path: str, params: dict | None = None) -> httpx2.Response:
    # trust_env=False：測試機上的 HTTP_PROXY 之類設定不能影響對 127.0.0.1 的請求
    with httpx2.Client(trust_env=False, timeout=5) as http:
        return http.get(f"http://127.0.0.1:{port}{path}", params=params)


def is_closed(port: int) -> bool:
    try:
        get(port, "/callback")
    except httpx2.TransportError:
        return True
    return False


def wait_closed(port: int, seconds: float = 3.0) -> bool:
    deadline = threading.Event()
    for _ in range(int(seconds / 0.05)):
        if is_closed(port):
            return True
        deadline.wait(0.05)
    return False


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture
def listener():
    created: list[LoopbackListener] = []

    def make(port: int | None = None) -> LoopbackListener:
        created.append(LoopbackListener.bind(port))
        return created[-1]

    yield make
    for item in created:
        item.close()


def test_os_assigns_port_when_none_is_configured(listener) -> None:
    assert listener().port >= 1024


def test_fixed_port_is_used_when_configured(listener) -> None:
    port = free_port()

    assert listener(port).port == port


def test_callback_parameters_reach_handler_and_final_result_closes_listener(listener) -> None:
    received: list[dict] = []
    server = listener()
    server.serve(lambda params: received.append(params) or AttemptResult.SUCCEEDED, timeout_seconds=30, on_timeout=lambda: None)

    response = get(server.port, "/callback", {"state": "53682.abc", "code": "4/CODE"})

    assert response.status_code == 200
    assert "授權完成" in response.text
    assert received == [{"state": "53682.abc", "code": "4/CODE"}]
    assert wait_closed(server.port)


def test_rejected_request_gets_400_and_listener_keeps_waiting(listener) -> None:
    answers = iter([None, AttemptResult.DENIED])
    server = listener()
    server.serve(lambda params: next(answers), timeout_seconds=30, on_timeout=lambda: None)

    first = get(server.port, "/callback", {"state": "noise"})
    second = get(server.port, "/callback", {"state": "real", "error": "access_denied"})

    assert first.status_code == 400
    assert second.status_code == 200
    assert "拒絕" in second.text


def test_other_paths_get_404_without_calling_handler(listener) -> None:
    calls: list[dict] = []
    server = listener()
    server.serve(lambda params: calls.append(params), timeout_seconds=30, on_timeout=lambda: None)

    assert get(server.port, "/favicon.ico").status_code == 404
    assert calls == []


def test_timeout_calls_back_and_closes_listener(listener) -> None:
    timed_out = threading.Event()
    server = listener()
    server.serve(lambda params: None, timeout_seconds=0.2, on_timeout=timed_out.set)

    assert timed_out.wait(3)
    assert wait_closed(server.port)


def test_close_releases_port_and_can_be_called_twice(listener) -> None:
    server = listener()
    server.serve(lambda params: None, timeout_seconds=30, on_timeout=lambda: None)

    server.close()
    server.close()

    assert is_closed(server.port)


def test_handler_crash_returns_failure_page_and_keeps_waiting(listener) -> None:
    answers = iter([RuntimeError("bug"), AttemptResult.SUCCEEDED])

    def handler(params: dict) -> AttemptResult | None:
        answer = next(answers)
        if isinstance(answer, Exception):
            raise answer
        return answer

    server = listener()
    server.serve(handler, timeout_seconds=30, on_timeout=lambda: None)

    assert get(server.port, "/callback", {"state": "x"}).status_code == 500
    assert get(server.port, "/callback", {"state": "y"}).status_code == 200


@pytest.mark.parametrize("result", [None, *AttemptResult], ids=lambda r: str(r))
def test_result_pages_never_reflect_request_parameters(listener, result) -> None:
    # A7：不論結果是什麼，頁面都只有固定訊息
    server = listener()
    server.serve(lambda params: result, timeout_seconds=30, on_timeout=lambda: None)

    response = get(server.port, "/callback", {"state": INJECTION, "error": INJECTION, "code": INJECTION})

    assert "alert(1)" not in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_requests_are_not_logged(listener, capfd: pytest.CaptureFixture) -> None:
    # stdout 是 MCP 的通訊管道；stderr 會進 Claude Code 的 log。兩邊都不能出現 code
    server = listener()
    server.serve(lambda params: AttemptResult.SUCCEEDED, timeout_seconds=30, on_timeout=lambda: None)

    get(server.port, "/callback", {"state": "x", "code": "4/SECRET-CODE"})
    wait_closed(server.port)

    out, err = capfd.readouterr()
    assert "SECRET-CODE" not in out + err


def test_close_without_serving_does_not_hang(listener) -> None:
    # 例如 bind 之後才發現 port 不合 B2 的範圍，呼叫端直接關掉
    server = listener()
    closer = threading.Thread(target=server.close)
    closer.start()
    closer.join(3)

    assert not closer.is_alive()
