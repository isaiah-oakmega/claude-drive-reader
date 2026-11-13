"""`python -m mcp_server`：plugin 的 .mcp.json 啟動的進入點，也是組裝根。

所有實例都在這裡建立，再透過建構子傳進 context 的 app/；context 自己不知道設定從哪裡來。
"""

import logging
import os
import sys
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from drive_reading.app import DriveReadingService
from drive_reading.infra import http_client as drive_http
from drive_reading.infra.drive_api import DriveApi
from local_authorization.app import AccessTokenProvider, AuthorizationService
from local_authorization.infra import browser
from local_authorization.infra.broker_client import BrokerClient
from local_authorization.infra.credential_store import CredentialStore
from local_authorization.infra.google_account import GoogleAccount
from local_authorization.infra.google_revoke import GoogleRevoker
from local_authorization.infra import http_client as auth_http
from mcp_server import tools
from mcp_server.config import Config, InvalidConfig


def build_server(config: Config) -> MCPServer:
    # httpx2 在 INFO 層級會記下每個請求的完整網址（Drive 的檔案 ID、查詢條件），而 stderr 會進 Claude Code 的 log。
    # token 不在網址裡，但這些資訊沒有必要留下；只保留 WARNING 以上的訊息。
    logging.getLogger("httpx2").setLevel(logging.WARNING)

    http = auth_http.new_http_client()
    store = CredentialStore(config.credentials_path)
    broker = BrokerClient(config.broker_url, http)
    token_provider = AccessTokenProvider(store=store, broker=broker, account=GoogleAccount(http))
    authorization = AuthorizationService(
        broker=broker,
        store=store,
        tokens=token_provider,
        revoker=GoogleRevoker(http),
        open_browser=browser.open_url,
        callback_port=config.callback_port,
    )

    # C2：Drive Reading 拿到的是 token provider，不知道 token 從哪裡來
    drive = DriveReadingService(DriveApi(drive_http.new_http_client(), token_provider), config.root_folder)

    server = MCPServer("drive-reader", instructions=tools.SERVER_INSTRUCTIONS)
    tools.register_authorization_tools(server, authorization)
    tools.register_drive_tools(server, drive, account=token_provider.current_account)
    return server


def main() -> None:
    # Windows 的 stderr 預設用系統的 code page，中文訊息會變成 \u 跳脫字元；統一用 UTF-8
    # （stdout 由 MCP SDK 自己以 UTF-8 包裝，不需要處理）
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    try:
        config = Config.from_env(os.environ, home=Path.home())
    except InvalidConfig as error:
        # stdout 是 MCP 的通訊管道，錯誤只能寫到 stderr；Claude Code 會在 /mcp 顯示啟動失敗並記錄 stderr
        print(f"Drive Reader 設定錯誤：{error}", file=sys.stderr)
        sys.exit(2)
    build_server(config).run()


if __name__ == "__main__":
    main()
