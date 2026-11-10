"""C5 設定合約：本機 MCP server 讀取的環境變數。設定錯誤時啟動就失敗，不要等到使用者授權時才發現。"""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from drive_reading.app import NotFoundOrNoAccess, parse_drive_id
from local_authorization.domain.limits import MAX_CALLBACK_PORT, MIN_CALLBACK_PORT

DEFAULT_BROKER_URL = "https://drive-auth.isaiahlin.dev"
# 出題方提供的測試資料夾。開發時用 DRIVE_READER_ROOT_FOLDER 指到自己的資料夾
DEFAULT_ROOT_FOLDER = "1AU6ZW-3NFxme6388YPe98bGWWh9q_E5Y"

# 只接受 ASCII 數字：int() 會把全形數字「５３６８２」也當成 53682
_PORT_PATTERN = re.compile(r"[0-9]{1,5}", re.ASCII)


class InvalidConfig(Exception):
    """訊息只說哪個變數、該是什麼樣子，不回顯使用者設定的值。"""


@dataclass(frozen=True)
class Config:
    broker_url: str
    # 已解析成 ID：設定的是網址也一樣
    root_folder: str
    credentials_path: Path
    # None 代表交給 OS 分配隨機 port（預設）；只有 SSH port forwarding 這類進階用法才需要固定
    callback_port: int | None

    @classmethod
    def from_env(cls, environ: Mapping[str, str], home: Path) -> "Config":
        def value(name: str) -> str | None:
            # 空字串視為沒設定：.mcp.json 的 env 或 shell 可能留下空值
            raw = environ.get(name, "").strip()
            return raw or None

        broker_url = value("DRIVE_READER_BROKER_URL") or DEFAULT_BROKER_URL
        parts = urlsplit(broker_url)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise InvalidConfig("DRIVE_READER_BROKER_URL 必須是完整的網址，例如 https://drive-auth.example.com")

        credentials = value("DRIVE_READER_CREDENTIALS_PATH")
        credentials_path = (
            _expand_home(Path(credentials), home)
            if credentials
            else home / ".config" / "claude-drive-reader" / "credentials.json"
        )

        port_text = value("DRIVE_READER_CALLBACK_PORT")
        callback_port = None
        if port_text is not None:
            if not _PORT_PATTERN.fullmatch(port_text) or not MIN_CALLBACK_PORT <= int(port_text) <= MAX_CALLBACK_PORT:
                # 必須符合 B2：Broker 只會把 code 轉到 1024–65535 的 port
                raise InvalidConfig(
                    f"DRIVE_READER_CALLBACK_PORT 必須是 {MIN_CALLBACK_PORT}–{MAX_CALLBACK_PORT} 的整數；"
                    "不需要固定 port 時請移除這個設定"
                )
            callback_port = int(port_text)

        try:
            # 解析規則屬於 Drive Reading；這裡只是在啟動時就呼叫它，設定錯了不必等到第一次列檔案才發現
            root_folder = parse_drive_id(value("DRIVE_READER_ROOT_FOLDER") or DEFAULT_ROOT_FOLDER)
        except NotFoundOrNoAccess:
            raise InvalidConfig("DRIVE_READER_ROOT_FOLDER 必須是 Google Drive 資料夾的 ID 或網址") from None

        return cls(
            broker_url=broker_url,
            root_folder=root_folder,
            credentials_path=credentials_path,
            callback_port=callback_port,
        )


def _expand_home(path: Path, home: Path) -> Path:
    # 自己展開 "~" 而不是用 Path.expanduser：home 由呼叫端傳入，測試不必依賴執行測試的那台機器
    if path.parts and path.parts[0] == "~":
        return home.joinpath(*path.parts[1:])
    return path
