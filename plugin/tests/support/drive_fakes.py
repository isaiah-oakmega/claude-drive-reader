"""Drive Reading 測試用的假 Drive：記憶體裡的一棵樹，介面和 infra/drive_api.DriveApi 相同。"""

from collections.abc import Iterator

from drive_reading.domain.drive_item import FOLDER_MIME, SHORTCUT_MIME, DriveItem
from drive_reading.domain.errors import NotFoundOrNoAccess
from drive_reading.infra.drive_api import DownloadTooLarge, ExportTooLarge

ROOT_ID = "root-folder-id-0001"


def folder(item_id: str, parent: str | None, name: str | None = None) -> DriveItem:
    return DriveItem(id=item_id, name=name or item_id, mime_type=FOLDER_MIME, parents=(parent,) if parent else ())


def file(item_id: str, parent: str, name: str | None = None, size: int | None = 1024, mime: str = "application/pdf") -> DriveItem:
    return DriveItem(
        id=item_id,
        name=name or item_id,
        mime_type=mime,
        parents=(parent,),
        size=size,
        modified_time="2026-11-01T10:00:00.000Z",
    )


def shortcut(item_id: str, parent: str, target_id: str, target_mime: str = "application/pdf", name: str | None = None) -> DriveItem:
    return DriveItem(
        id=item_id,
        name=name or item_id,
        mime_type=SHORTCUT_MIME,
        parents=(parent,),
        shortcut_target_id=target_id,
        shortcut_target_mime_type=target_mime,
    )


class FakeDrive:
    """hidden 裡的 ID 對目前的帳號來說「看不到」，行為和 Drive 回 404 一樣。

    contents 是一般檔案的內容；exports 以 (ID, 匯出格式) 對應匯出的內容。
    export_too_large 裡的 ID 匯出時，模擬 Google 回 exportSizeLimitExceeded。
    """

    def __init__(self, *items: DriveItem, hidden: set[str] | None = None) -> None:
        self.items = {item.id: item for item in items}
        self.hidden = hidden or set()
        self.listed: list[str] = []
        self.contents: dict[str, bytes] = {}
        self.exports: dict[tuple[str, str], bytes] = {}
        self.export_too_large: set[str] = set()
        self.downloaded: list[str] = []

    def download(self, item_id: str, max_bytes: int) -> bytes:
        self.get_item(item_id)
        self.downloaded.append(item_id)
        return self._capped(self.contents[item_id], max_bytes)

    def export(self, item_id: str, mime_type: str, max_bytes: int) -> bytes:
        self.get_item(item_id)
        self.downloaded.append(item_id)
        if item_id in self.export_too_large:
            raise ExportTooLarge
        return self._capped(self.exports[(item_id, mime_type)], max_bytes)

    @staticmethod
    def _capped(data: bytes, max_bytes: int) -> bytes:
        if len(data) > max_bytes:
            raise DownloadTooLarge
        return data

    def get_item(self, item_id: str) -> DriveItem:
        item = self.find_item(item_id)
        if item is None:
            raise NotFoundOrNoAccess(item_id)
        return item

    def find_item(self, item_id: str) -> DriveItem | None:
        return None if item_id in self.hidden else self.items.get(item_id)

    def list_children(self, parent: DriveItem) -> Iterator[DriveItem]:
        self.listed.append(parent.id)
        yield from (item for item in self.items.values() if item.parents[:1] == (parent.id,) and item.id not in self.hidden)


def sample_drive() -> FakeDrive:
    """Root Folder 底下有子資料夾、捷徑；Root Folder 外面還有一個別人的資料夾。"""
    return FakeDrive(
        folder(ROOT_ID, "my-drive", "Drive Reader 測試"),
        folder("reports-id-0001", ROOT_ID, "報告"),
        file("q1-id-000001", "reports-id-0001", "q1.pdf"),
        file("readme-id-0001", ROOT_ID, "readme.txt", size=120, mime="text/plain"),
        DriveItem(id="doc-id-000001", name="會議記錄", mime_type="application/vnd.google-apps.document", parents=(ROOT_ID,)),
        shortcut("link-id-00001", ROOT_ID, "outside-file-01", name="外部連結"),
        folder("outside-dir-01", "my-drive", "別人的資料夾"),
        file("outside-file-01", "outside-dir-01", "secret.pdf"),
        folder("my-drive", None, "My Drive"),
    )
