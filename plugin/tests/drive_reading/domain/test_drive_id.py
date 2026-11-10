"""資料夾與檔案參數接受純 ID 或 Drive URL，解析後統一成 ID（實作規格「驗證與呈現」）。"""

import pytest

from drive_reading.domain.drive_id import parse_drive_id
from drive_reading.domain.errors import NotFoundOrNoAccess

ID = "1VZWKGbpdNVHAK1y9lXhndLquS80gcemn"


@pytest.mark.parametrize(
    "text",
    [
        ID,
        f"  {ID}  ",
        f"https://drive.google.com/drive/folders/{ID}",
        f"https://drive.google.com/drive/folders/{ID}?usp=sharing",
        f"https://drive.google.com/drive/u/1/folders/{ID}",
        f"https://drive.google.com/file/d/{ID}/view?usp=drive_link",
        f"https://docs.google.com/document/d/{ID}/edit",
        f"https://docs.google.com/spreadsheets/d/{ID}/edit#gid=0",
        f"https://docs.google.com/presentation/d/{ID}/edit",
        f"https://drive.google.com/open?id={ID}",
        f"https://drive.google.com/uc?id={ID}&export=download",
    ],
    ids=["id", "padded", "folder", "folder-query", "folder-user", "file", "doc", "sheet", "slides", "open", "uc"],
)
def test_ids_and_drive_urls_resolve_to_the_id(text: str) -> None:
    assert parse_drive_id(text) == ID


@pytest.mark.parametrize(
    "text",
    [
        "",
        "short",
        "../../etc/passwd",
        f"{ID}' or name contains 'x",
        f"https://evil.example/drive/folders/{ID}",
        "https://drive.google.com/drive/my-drive",
        "https://drive.google.com/drive/folders/",
    ],
    ids=["empty", "too-short", "path", "query-injection", "other-host", "no-id", "empty-id"],
)
def test_anything_else_is_not_found(text: str) -> None:
    # 不合格的參數一律當成「找不到」：它不可能指向 Root Folder 內的任何東西。
    # 只接受 ID 字元也確保 ID 放進 Drive 的查詢字串時，不能夾帶其他查詢條件。
    with pytest.raises(NotFoundOrNoAccess):
        parse_drive_id(text)
