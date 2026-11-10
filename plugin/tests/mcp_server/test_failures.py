"""C3 的 Failure 格式：[代碼] 原因。下一步：…"""

import re

import pytest

from local_authorization.app import AuthExpired, BrokerUnreachable, CallbackPortUnavailable, NotAuthorized
from mcp_server.failures import failure_text

FORMAT = re.compile(r"\[(?P<code>[A-Z_]+)\] .+。下一步：.+")


@pytest.mark.parametrize(
    "error, code",
    [
        (NotAuthorized(), "NOT_AUTHORIZED"),
        (AuthExpired(), "AUTH_EXPIRED"),
        (BrokerUnreachable("https://broker.example"), "BROKER_UNREACHABLE"),
        (CallbackPortUnavailable(50000), "CALLBACK_PORT_UNAVAILABLE"),
    ],
)
def test_authorization_failures_have_code_and_next_step(error: Exception, code: str) -> None:
    text = failure_text(error)

    match = FORMAT.fullmatch(text)
    assert match is not None, text
    assert match["code"] == code


def test_not_authorized_and_expired_point_to_authorize() -> None:
    assert "authorize" in failure_text(NotAuthorized()).split("下一步：")[1]
    assert "authorize" in failure_text(AuthExpired()).split("下一步：")[1]


def test_broker_unreachable_includes_broker_url() -> None:
    # 情境 14：附上 Broker 網址，使用者才能判斷是不是設定錯了
    assert "https://broker.example" in failure_text(BrokerUnreachable("https://broker.example"))


def test_callback_port_failure_names_port_and_setting() -> None:
    text = failure_text(CallbackPortUnavailable(50000))

    assert "50000" in text
    assert "DRIVE_READER_CALLBACK_PORT" in text.split("下一步：")[1]


def test_unknown_errors_are_not_formatted() -> None:
    # 程式錯誤不偽裝成 Failure，交給 MCP SDK 當成 crash 處理
    assert failure_text(RuntimeError("bug")) is None
