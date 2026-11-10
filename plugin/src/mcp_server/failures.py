"""領域例外 → C3 的 Failure 文字：[代碼] 原因。下一步：…

讀這段文字的是 Claude，它會轉述給使用者，所以「下一步」寫成 Claude 能照做或能轉告的動作。
"""

from local_authorization.app import AuthExpired, AuthorizationError, BrokerUnreachable, CallbackPortUnavailable, NotAuthorized

# tool 層要攔下並轉成 Failure 的例外；其他例外是程式錯誤，交給 MCP SDK 當成 crash
KNOWN_FAILURES: tuple[type[Exception], ...] = (AuthorizationError, CallbackPortUnavailable)


def failure_text(error: Exception) -> str | None:
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
            # C3 沒有這個情況的代碼（只會在固定 port 被占用時發生），所以不加代碼，只給原因與下一步
            return (
                f"無法在本機 127.0.0.1:{port} 等待授權結果，這個 port 可能已被其他程式使用。"
                "下一步：把 DRIVE_READER_CALLBACK_PORT 改成其他 port，或移除這個設定讓系統自動選擇"
            )
    return None


def _format(code: str, reason: str, next_step: str) -> str:
    return f"[{code}] {reason}。下一步：{next_step}"
