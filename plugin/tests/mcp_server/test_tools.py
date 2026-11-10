"""C3：授權相關的三個 tool。透過 MCPServer 實際呼叫，背後的 use case 是假的（use case 本身有自己的測試）。"""

from pathlib import Path

import anyio
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from local_authorization.app import (
    AttemptResult,
    AuthorizationStarted,
    AuthStatus,
    CallbackPortUnavailable,
    LogoutReport,
    RevokeOutcome,
)
from mcp_server import tools

URL = "https://broker.example/authorize?state=53682.abc&code_challenge=xyz"


def status(**overrides) -> AuthStatus:
    values = dict(
        authorized=False,
        account=None,
        attempt_in_progress=False,
        last_result=None,
        credentials_path=Path("/home/someone/.config/claude-drive-reader/credentials.json"),
        permissions_enforced=True,
    )
    return AuthStatus(**(values | overrides))


class FakeAuthorization:
    def __init__(self) -> None:
        self.started = AuthorizationStarted(url=URL, browser_opened=True, expires_in_seconds=300)
        self.authorize_error: Exception | None = None
        self.current = status()
        self.report = LogoutReport(had_credential=True, revoke=RevokeOutcome.REVOKED, deleted=True)

    def authorize(self) -> AuthorizationStarted:
        if self.authorize_error is not None:
            raise self.authorize_error
        return self.started

    def status(self) -> AuthStatus:
        return self.current

    def logout(self) -> LogoutReport:
        return self.report


@pytest.fixture
def auth() -> FakeAuthorization:
    return FakeAuthorization()


@pytest.fixture
def server(auth: FakeAuthorization) -> MCPServer:
    server = MCPServer("test")
    tools.register_authorization_tools(server, auth)
    return server


def call(server: MCPServer, name: str) -> str:
    result = anyio.run(server.call_tool, name, {})
    assert result.is_error is False
    return "\n".join(block.text for block in result.content)


# ---------- 註冊與 schema ----------


def test_tools_are_registered_without_required_parameters(server: MCPServer) -> None:
    listed = {tool.name: tool for tool in anyio.run(server.list_tools)}

    assert set(listed) == {"authorize", "auth_status", "logout"}
    for tool in listed.values():
        assert not tool.input_schema.get("required")
        # 描述中英雙語：至少要有中文的常見說法
        assert tool.description and any("一" <= ch <= "鿿" for ch in tool.description)


# ---------- authorize ----------


def test_authorize_returns_url_and_asks_user_to_report_back(server: MCPServer) -> None:
    text = call(server, "authorize")

    assert URL in text
    assert "完成後" in text
    assert "進階" in text  # 未驗證警告的操作說明
    assert "5 分鐘" in text


def test_authorize_says_when_browser_did_not_open(server: MCPServer, auth: FakeAuthorization) -> None:
    auth.started = AuthorizationStarted(url=URL, browser_opened=False, expires_in_seconds=300)

    assert "無法自動開啟瀏覽器" in call(server, "authorize")


def test_authorize_failure_is_reported_as_tool_error(server: MCPServer, auth: FakeAuthorization) -> None:
    auth.authorize_error = CallbackPortUnavailable(50000)

    with pytest.raises(ToolError, match=r"\[CALLBACK_PORT_UNAVAILABLE\].*DRIVE_READER_CALLBACK_PORT"):
        anyio.run(server.call_tool, "authorize", {})


# ---------- auth_status ----------


def test_status_when_not_authorized(server: MCPServer) -> None:
    text = call(server, "auth_status")

    assert "尚未授權" in text
    assert "上一次授權的結果：無" in text


@pytest.mark.parametrize(
    "result, label",
    [
        (AttemptResult.SUCCEEDED, "成功"),
        (AttemptResult.DENIED, "已拒絕"),
        (AttemptResult.TIMED_OUT, "逾時"),
        (AttemptResult.FAILED, "失敗"),
    ],
)
def test_status_reports_last_attempt_result(server: MCPServer, auth: FakeAuthorization, result: AttemptResult, label: str) -> None:
    auth.current = status(last_result=result)

    assert f"上一次授權的結果：{label}" in call(server, "auth_status")


def test_status_when_authorized_shows_account_and_attempt(server: MCPServer, auth: FakeAuthorization) -> None:
    auth.current = status(authorized=True, account="someone@example.com", attempt_in_progress=True)

    text = call(server, "auth_status")

    assert "已授權" in text and "someone@example.com" in text
    assert "進行中的授權：有" in text


def test_status_describes_file_protection_per_platform(server: MCPServer, auth: FakeAuthorization) -> None:
    # A4：只有 POSIX 才宣稱 0600
    assert "0600" in call(server, "auth_status")

    auth.current = status(permissions_enforced=False)
    text = call(server, "auth_status")
    assert "0600" not in text
    assert "Windows" in text


# ---------- logout ----------


@pytest.mark.parametrize(
    "report, expected",
    [
        (LogoutReport(had_credential=True, revoke=RevokeOutcome.REVOKED, deleted=True), "已向 Google 撤銷授權"),
        (LogoutReport(had_credential=True, revoke=RevokeOutcome.ALREADY_INVALID, deleted=True), "本來就已失效"),
        (LogoutReport(had_credential=True, revoke=RevokeOutcome.FAILED, deleted=True), "撤銷失敗"),
        (LogoutReport(had_credential=False, revoke=None, deleted=False), "目前沒有授權"),
    ],
    ids=["revoked", "already-invalid", "revoke-failed", "not-logged-in"],
)
def test_logout_reports_revoke_and_delete(server: MCPServer, auth: FakeAuthorization, report: LogoutReport, expected: str) -> None:
    auth.report = report

    text = call(server, "logout")

    assert expected in text
    if report.had_credential:
        assert "已刪除" in text


def test_failed_revoke_tells_user_how_to_remove_access_manually(server: MCPServer, auth: FakeAuthorization) -> None:
    auth.report = LogoutReport(had_credential=True, revoke=RevokeOutcome.FAILED, deleted=True)

    assert "myaccount.google.com/permissions" in call(server, "logout")
