"""領域例外 → C3 的 Failure 文字：[代碼] 原因。下一步：…

讀這段文字的是 Claude，它會轉述給使用者，所以「下一步」寫成 Claude 能照做或能轉告的動作。
"""

from collections.abc import Callable

from drive_reading.app import DriveReadingError, GoogleApiError, NotAFile, NotFoundOrNoAccess, OutsideRoot
from local_authorization.app import AuthExpired, AuthorizationError, BrokerUnreachable, CallbackPortUnavailable, NotAuthorized

# tool 層要攔下並轉成 Failure 的例外；其他例外是程式錯誤，交給 MCP SDK 當成 crash
KNOWN_FAILURES: tuple[type[Exception], ...] = (AuthorizationError, CallbackPortUnavailable, DriveReadingError)


def failure_text(error: Exception, account: Callable[[], str | None] = lambda: None) -> str | None:
    """account 只在 NOT_FOUND_OR_NO_ACCESS 時才呼叫：查 email 是一次額外的 Drive API 呼叫。"""
    match error:
        case NotAuthorized():
            return _format(
                "NOT_AUTHORIZED",
                "還沒有授權 Drive Reader 讀取 Google Drive",
                "呼叫 authorize 取得授權網址，請使用者在瀏覽器完成授權後再試一次",
            )
        case AuthExpired():
            return _format(
                "AUTH_EXPIRED",
                "Google 授權已失效（可能已被撤銷或過期），本機保存的授權已清除",
                "呼叫 authorize 重新授權後再試一次",
            )
        case BrokerUnreachable(broker_url=url):
            return _format(
                "BROKER_UNREACHABLE",
                f"無法透過 Token Broker（{url}）取得 token",
                "確認網路連線後再試一次；如果有設定 DRIVE_READER_BROKER_URL，請確認網址正確",
            )
        case CallbackPortUnavailable(port=port):
            # 只會在設定固定 port 時發生；預設由 OS 分配沒人使用的 port
            return _format(
                "CALLBACK_PORT_UNAVAILABLE",
                f"無法在本機 127.0.0.1:{port} 等待授權結果，這個 port 可能已被其他程式使用",
                "把 DRIVE_READER_CALLBACK_PORT 改成其他 port，或移除這個設定讓系統自動選擇",
            )
        case NotFoundOrNoAccess(reference=reference):
            # R6：Drive 對「沒有權限」也回 404，所以兩種可能都要說，並附上目前的帳號（情境 11）
            email = account() or "無法取得 email"
            return _format(
                "NOT_FOUND_OR_NO_ACCESS",
                f"找不到 {reference}，或目前授權的帳號（{email}）沒有存取權",
                "確認 ID 或網址正確；如果是別人分享的資料夾，請先用這個帳號接受分享邀請，"
                "或呼叫 logout 後改用有權限的帳號重新 authorize",
            )
        case OutsideRoot(reference=reference):
            # 情境 13：只把 Claude 導回 Root Folder 內，不提供任何繞過邊界的方法
            return _format(
                "OUTSIDE_ROOT",
                f"{reference} 不在設定的 Root Folder 範圍內，Drive Reader 不會讀取它",
                "只使用 list_files 列出的項目；如果使用者確實需要其他資料夾，請使用者自行修改 DRIVE_READER_ROOT_FOLDER 設定",
            )
        case NotAFile(reference=reference):
            return _format(
                "NOT_A_FILE",
                f"{reference} 是資料夾，不是檔案",
                "用 list_files 列出這個資料夾的內容，再用 read_file 讀取其中的檔案",
            )
        case GoogleApiError(status=status, reason=reason):
            where = f"HTTP {status}" if status is not None else "沒有收到回應"
            return _format(
                "GOOGLE_API_ERROR",
                f"Google Drive 回傳錯誤（{where}：{reason}）",
                "稍後再試一次；如果持續發生，把這段錯誤告訴使用者",
            )
    return None


def _format(code: str, reason: str, next_step: str) -> str:
    return f"[{code}] {reason}。下一步：{next_step}"
