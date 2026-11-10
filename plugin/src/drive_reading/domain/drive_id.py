"""把使用者給的 ID 或 Drive 網址統一成 ID。"""

import re
from urllib.parse import parse_qs, urlsplit

from drive_reading.domain.errors import NotFoundOrNoAccess

# Drive 的 ID 只由英數字、"-"、"_" 組成。只接受這些字元，ID 放進 files.list 的查詢字串
# （例如 "'<id>' in parents"）時，就不可能夾帶引號去改變查詢條件。
_ID = re.compile(r"[A-Za-z0-9_-]{10,}", re.ASCII)
# /drive/folders/<id>、/file/d/<id>、/document/d/<id> 這類路徑
_ID_IN_PATH = re.compile(r"/(?:folders|d)/([A-Za-z0-9_-]+)", re.ASCII)
_GOOGLE_HOSTS = ("drive.google.com", "docs.google.com")


def parse_drive_id(text: str) -> str:
    candidate = text.strip()
    if candidate.startswith(("http://", "https://")):
        candidate = _id_from_url(candidate) or ""
    if not _ID.fullmatch(candidate):
        raise NotFoundOrNoAccess(text.strip())
    return candidate


def _id_from_url(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.hostname not in _GOOGLE_HOSTS:
        # 其他網站的網址就算長得像 Drive，也不是 Drive 的項目
        return None
    match = _ID_IN_PATH.search(parts.path)
    if match:
        return match.group(1)
    # /open?id=<id>、/uc?id=<id>
    ids = parse_qs(parts.query).get("id")
    return ids[0] if ids else None
