"""依 mimeType 決定怎麼取得內容（C4 的匯出格式、實作規格「檔案類型處理」）。"""

from enum import Enum

# C4：Google 原生格式只能匯出，不能直接下載
_EXPORT_FORMATS = {
    "application/vnd.google-apps.document": "text/markdown",
    # CSV 只能表示一個工作表，Drive 只會匯出第一個（回傳時要註明）
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}
SPREADSHEET_MIME = "application/vnd.google-apps.spreadsheet"

# 不是 text/* 但內容其實是文字的常見格式
_TEXT_APPLICATION_TYPES = {
    "application/json",
    "application/xml",
    "application/javascript",
    "application/x-javascript",
    "application/x-yaml",
    "application/yaml",
    "application/x-sh",
    "application/sql",
    # SVG 是 XML 文字，以文字回傳比算繪成圖片更能讓 Claude 讀懂內容
    "image/svg+xml",
}


class ContentKind(Enum):
    GOOGLE_EXPORT = "google_export"
    PDF = "pdf"
    IMAGE = "image"
    TEXT = "text"
    UNSUPPORTED = "unsupported"


def classify(mime_type: str) -> ContentKind:
    if mime_type in _EXPORT_FORMATS:
        return ContentKind.GOOGLE_EXPORT
    if mime_type == "application/pdf":
        return ContentKind.PDF
    if mime_type.startswith("text/") or mime_type in _TEXT_APPLICATION_TYPES:
        return ContentKind.TEXT
    if mime_type.startswith("image/"):
        # Pillow 打不開的格式（例如 HEIC）在處理時才會知道，到時候回報 Read Limitation
        return ContentKind.IMAGE
    # 其他 Google 原生格式（表單、繪圖……）、Office 檔案、壓縮檔、影音都不解析（Out of Scope）
    return ContentKind.UNSUPPORTED


def export_format(mime_type: str) -> str:
    return _EXPORT_FORMATS[mime_type]
