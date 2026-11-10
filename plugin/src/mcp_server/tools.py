"""C3 的 MCP tools。這裡只做轉接與格式化：參數交給 context 的 app/，結果轉成給 Claude 看的繁中文字。"""

from collections.abc import Callable, Iterator
from contextlib import contextmanager

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from drive_reading.app import DriveItem, DriveReadingService, FolderListing
from drive_reading.domain.limits import MAX_LIST_DEPTH, MAX_LIST_ITEMS
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
def _failures_as_tool_errors(account: Callable[[], str | None] = lambda: None) -> Iterator[None]:
    # ToolError 讓 MCP 回 is_error=True 並把文字交給 Claude；其他例外維持原樣，由 SDK 當成 crash 處理
    try:
        yield
    except KNOWN_FAILURES as error:
        raise ToolError(failure_text(error, account)) from error


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


# ---------- Drive Reading ----------


def register_drive_tools(server: MCPServer, drive: DriveReadingService, account: Callable[[], str | None]) -> None:
    @server.tool(
        description=(
            "List files in the user's configured Google Drive Root Folder, or in a folder inside it. "
            "Returns one line per item: relative path, mimeType, size, modified time, and ID. "
            "Parameters: folder (optional ID or Drive URL of a folder inside the Root Folder; omit to list the "
            "Root Folder), recursive (default true; false lists only direct children). "
            "列出資料夾內的檔案。常見說法：「這個資料夾有什麼」「列出檔案」「有哪些 PDF」「子資料夾裡有什麼」。"
        )
    )
    def list_files(folder: str | None = None, recursive: bool = True) -> str:
        with _failures_as_tool_errors(account):
            result = drive.list_files(folder=folder, recursive=recursive)
        return _describe_listing(result, recursive)


def _describe_listing(result: FolderListing, recursive: bool) -> str:
    listing = result.listing
    lines = [f"Root Folder：{result.root.name}"]
    if result.folder_path:
        kind = "資料夾" if result.folder.is_folder else "項目"
        lines.append(f"列出的{kind}：{'/'.join(result.folder_path)}{'/' if result.folder.is_folder else ''}")
    if not result.folder.is_folder:
        lines.append("這是檔案，不是資料夾，以下只列出它本身。")
    elif not listing.entries:
        lines.append("這個資料夾是空的。")
        return "\n".join(lines)
    else:
        scope = f"包含子資料夾，最多 {MAX_LIST_DEPTH} 層" if recursive else "只列出直接的子項目"
        lines.append(f"共 {len(listing.entries)} 項（{scope}）：")

    lines.append("路徑 | 類型 | 大小 | 修改時間 | ID")
    lines += [_describe_item(entry.path, entry.item) for entry in listing.entries]

    if listing.truncated:
        lines.append(f"已達 {MAX_LIST_ITEMS} 筆上限，後面的項目沒有列出。可以用子資料夾的 ID 分別再列一次。")
    if listing.unexpanded:
        lines.append(f"以下資料夾位於第 {MAX_LIST_DEPTH} 層，沒有再往下列出：{'、'.join(listing.unexpanded)}")
    if listing.repeated:
        lines.append(f"以下資料夾重複出現，內容只列出一次：{'、'.join(listing.repeated)}")
    return "\n".join(lines)


def _describe_item(path: str, item: DriveItem) -> str:
    kind = item.mime_type
    if item.is_shortcut:
        # R2：列出時不跟進捷徑，只標示目標；要讀目標時再對目標套用 R1
        kind += f" → 目標 {item.shortcut_target_id}（{item.shortcut_target_mime_type}）"
    # 名稱裡的 "|" 會和欄位分隔混淆，換成全形
    return " | ".join([path.replace("|", "｜"), kind, _size(item.size), _time(item.modified_time), item.id])


def _size(size: int | None) -> str:
    if size is None:
        # Google 文件、試算表、資料夾沒有檔案大小
        return "—"
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{size} B" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _time(modified: str | None) -> str:
    # Drive 的格式是 RFC 3339（例如 2026-11-01T10:00:00.000Z），只保留到分鐘
    if not modified or len(modified) < 16:
        return "—"
    return f"{modified[:10]} {modified[11:16]} UTC"
