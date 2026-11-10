"""C3 的 MCP tools。這裡只做轉接與格式化：參數交給 context 的 app/，結果轉成給 Claude 看的繁中文字。"""

from collections.abc import Iterator
from contextlib import contextmanager

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from local_authorization.app import AttemptResult, AuthorizationService, AuthStatus, LogoutReport, RevokeOutcome
from mcp_server.failures import KNOWN_FAILURES, failure_text

_RESULT_LABELS = {
    None: "無（這次啟動後還沒有嘗試授權）",
    AttemptResult.SUCCEEDED: "成功",
    AttemptResult.DENIED: "已拒絕",
    AttemptResult.TIMED_OUT: "逾時（超過 5 分鐘沒有完成）",
    AttemptResult.FAILED: "失敗",
}
_REVOKE_LABELS = {
    RevokeOutcome.REVOKED: "已向 Google 撤銷授權",
    RevokeOutcome.ALREADY_INVALID: "Google 回報這個授權本來就已失效，不需要撤銷",
    RevokeOutcome.FAILED: (
        "向 Google 撤銷失敗（網路或 Google 暫時無法使用）。"
        "可以到 https://myaccount.google.com/permissions 手動移除 Drive Reader 的存取權"
    ),
}


@contextmanager
def _failures_as_tool_errors() -> Iterator[None]:
    # ToolError 讓 MCP 回 is_error=True 並把文字交給 Claude；其他例外維持原樣，由 SDK 當成 crash 處理
    try:
        yield
    except KNOWN_FAILURES as error:
        raise ToolError(failure_text(error)) from error


def register_authorization_tools(server: MCPServer, auth: AuthorizationService) -> None:
    @server.tool(
        description=(
            "Start Google Drive authorization. Returns a URL the user must open to grant read-only access. "
            "Call this when another Drive Reader tool reports NOT_AUTHORIZED or AUTH_EXPIRED, or when the user "
            "asks to connect, log in, or switch Google accounts. "
            "開始 Google Drive 授權，回傳要請使用者開啟的網址。常見說法：「授權」「登入 Google」「連接 Drive」「換帳號」。"
        )
    )
    def authorize() -> str:
        with _failures_as_tool_errors():
            started = auth.authorize()
        opened = "已嘗試自動開啟瀏覽器" if started.browser_opened else "無法自動開啟瀏覽器，請手動開啟"
        minutes = round(started.expires_in_seconds / 60)
        return (
            f"請開啟下列網址，用要讀取 Drive 的 Google 帳號完成授權（{opened}）：\n"
            f"{started.url}\n\n"
            "Google 會顯示「這個應用程式未經驗證」的警告：點「進階」，再點「前往…（不安全）」，然後同意唯讀存取。\n"
            f"網址在 {minutes} 分鐘內有效。完成後請告訴我，我再繼續。"
        )

    @server.tool(
        description=(
            "Show whether Google Drive is authorized, which Google account is used, whether an authorization is in "
            "progress, and the result of the last attempt. Use it after the user says they finished authorizing. "
            "查看授權狀態。常見說法：「授權好了嗎」「我現在是哪個帳號」「授權成功了嗎」。"
        )
    )
    def auth_status() -> str:
        return _describe_status(auth.status())

    @server.tool(
        description=(
            "Log out: revoke Drive Reader's Google access and delete the locally stored credential. "
            "登出並撤銷授權。常見說法：「登出」「取消授權」「換帳號」（先登出再重新授權）。"
        )
    )
    def logout() -> str:
        return _describe_logout(auth.logout())


def _describe_status(status: AuthStatus) -> str:
    if not status.authorized:
        authorized = "尚未授權"
    elif status.account:
        authorized = f"已授權（帳號：{status.account}）"
    else:
        authorized = "已授權（暫時無法取得帳號 email）"
    # A4：只有 POSIX 平台才宣稱 0600
    protection = (
        "檔案權限 0600，只有你的帳號能讀取"
        if status.permissions_enforced
        else "Windows：依使用者設定檔目錄的預設權限保護，程式不另外設定 ACL"
    )
    return "\n".join(
        [
            f"授權狀態：{authorized}",
            f"進行中的授權：{'有（等待瀏覽器完成）' if status.attempt_in_progress else '無'}",
            f"上一次授權的結果：{_RESULT_LABELS[status.last_result]}",
            f"授權保存位置：{status.credentials_path}（{protection}）",
        ]
    )


def _describe_logout(report: LogoutReport) -> str:
    if not report.had_credential:
        return "目前沒有授權，不需要登出。"
    deleted = "本機保存的授權已刪除" if report.deleted else "本機保存的授權已不存在（可能已被其他視窗刪除）"
    return f"已登出：{_REVOKE_LABELS[report.revoke]}；{deleted}。"
