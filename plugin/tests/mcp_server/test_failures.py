"""C3 的 Failure 格式：[代碼] 原因。下一步：…"""

import re

import pytest

from drive_reading.app import GoogleApiError, NotFoundOrNoAccess, OutsideRoot
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
        (NotFoundOrNoAccess("abc"), "NOT_FOUND_OR_NO_ACCESS"),
        (OutsideRoot("abc"), "OUTSIDE_ROOT"),
        (GoogleApiError(403, "insufficientFilePermissions"), "GOOGLE_API_ERROR"),
        (GoogleApiError(None, "無法連線到 Google Drive"), "GOOGLE_API_ERROR"),
    ],
)
def test_failures_have_code_and_next_step(error: Exception, code: str) -> None:
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


def test_not_found_names_the_authorized_account() -> None:
    # 情境 11：附上目前帳號的 email，使用者才看得出是不是用錯帳號
    text = failure_text(NotFoundOrNoAccess("abc"), account=lambda: "someone@example.com")

    assert "someone@example.com" in text
    next_step = text.split("下一步：")[1]
    assert "接受" in next_step and "logout" in next_step


def test_not_found_without_known_account_still_explains() -> None:
    assert FORMAT.fullmatch(failure_text(NotFoundOrNoAccess("abc"), account=lambda: None))


def test_account_is_looked_up_only_for_not_found() -> None:
    def must_not_be_called() -> str:
        raise AssertionError("about.get 是額外的 API 呼叫，只在需要時才做")

    failure_text(OutsideRoot("abc"), account=must_not_be_called)
    failure_text(NotAuthorized(), account=must_not_be_called)


def test_outside_root_does_not_suggest_working_around_the_boundary() -> None:
    # 情境 13：下一步只能把 Claude 導回 Root Folder 內，不能教它怎麼繞過
    next_step = failure_text(OutsideRoot("abc")).split("下一步：")[1]

    assert "list_files" in next_step


def test_google_api_error_includes_status_and_reason() -> None:
    text = failure_text(GoogleApiError(403, "insufficientFilePermissions"))

    assert "403" in text and "insufficientFilePermissions" in text
