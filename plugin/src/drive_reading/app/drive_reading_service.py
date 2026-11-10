"""Drive Reading 的 use case：list_files 與 read_file。"""

from dataclasses import dataclass

from drive_reading.domain.content_kind import SPREADSHEET_MIME, ContentKind, classify, export_format
from drive_reading.domain.drive_id import parse_drive_id
from drive_reading.domain.drive_item import DriveItem
from drive_reading.domain.errors import NotAFile
from drive_reading.domain.limits import MAX_DOWNLOAD_BYTES, MAX_TEXT_CHARS
from drive_reading.domain.listing import ListedEntry, Listing, build_listing
from drive_reading.domain.outcomes import (
    Content,
    FirstSheetOnly,
    LimitationReason,
    Note,
    ReadLimitation,
    TextPart,
    TextTruncated,
)
from drive_reading.domain.root_folder import path_from_root
from drive_reading.domain.text import truncate_text
from drive_reading.infra.content.image import prepare_image
from drive_reading.infra.content.pdf import read_pdf
from drive_reading.infra.content.text import decode_text
from drive_reading.infra.drive_api import DownloadTooLarge, DriveApi, ExportTooLarge


@dataclass(frozen=True)
class FolderListing:
    root: DriveItem
    folder: DriveItem
    # 從 Root Folder 底下到被列出項目的名稱路徑；列的是 Root Folder 本身時為空
    folder_path: tuple[str, ...]
    listing: Listing


@dataclass(frozen=True)
class FileRead:
    root: DriveItem
    # 實際讀取的檔案：透過捷徑讀取時是捷徑的目標
    item: DriveItem
    # 從 Root Folder 底下到使用者指定項目（捷徑時是捷徑本身）的名稱路徑
    path: tuple[str, ...]
    shortcut: DriveItem | None
    outcome: Content | ReadLimitation


class DriveReadingService:
    def __init__(self, drive: DriveApi, root_folder_id: str) -> None:
        self._drive = drive
        self._root_id = root_folder_id

    def list_files(self, folder: str | None = None, recursive: bool = True) -> FolderListing:
        # 先確認看得到 Root Folder：看不到時（帳號不對、還沒接受邀請）要回報的是這件事（情境 11），
        # 而不是讓使用者以為是他指定的子資料夾有問題
        root = self._drive.get_item(self._root_id)
        target_id = parse_drive_id(folder) if folder else self._root_id
        if target_id == self._root_id:
            target, path = root, ()
        else:
            target = self._drive.get_item(target_id)
            # R1：在列出任何內容之前，先確認目標在 Root Folder 子樹內
            path = path_from_root(target, self._root_id, self._drive.find_item)

        if target.is_folder:
            listing = build_listing(target, self._drive.list_children, recursive)
        else:
            # 指定的是檔案或捷徑：只列它自己，讓 Claude 看得到它的類型與 ID
            listing = Listing(entries=(ListedEntry(path=target.name, item=target),), truncated=False, unexpanded=(), repeated=())
        return FolderListing(root=root, folder=target, folder_path=path, listing=listing)

    def read_file(self, file: str) -> FileRead:
        root = self._drive.get_item(self._root_id)
        target_id = parse_drive_id(file)
        item = root if target_id == self._root_id else self._drive.get_item(target_id)
        # R1：先確認在 Root Folder 內，才會下載任何內容（情境 13）
        path = path_from_root(item, self._root_id, self._drive.find_item)

        shortcut = None
        if item.is_shortcut and item.shortcut_target_id:
            # R2：讀取時解析捷徑，並對「目標」再套用一次 R1
            shortcut = item
            item = self._drive.get_item(item.shortcut_target_id)
            path_from_root(item, self._root_id, self._drive.find_item)
        if item.is_folder:
            raise NotAFile(item.id)
        return FileRead(root=root, item=item, path=path, shortcut=shortcut, outcome=self._read(item))

    def _read(self, item: DriveItem) -> Content | ReadLimitation:
        kind = classify(item.mime_type)
        if kind is ContentKind.UNSUPPORTED:
            # 情境 10：不支援的類型不下載
            return ReadLimitation(LimitationReason.UNSUPPORTED_TYPE)
        if item.size is not None and item.size > MAX_DOWNLOAD_BYTES:
            # R4 的第一道檢查：有 size 就先判斷，超過就不下載
            return ReadLimitation(LimitationReason.TOO_LARGE)
        try:
            if kind is ContentKind.GOOGLE_EXPORT:
                data = self._drive.export(item.id, export_format(item.mime_type), MAX_DOWNLOAD_BYTES)
                extra: tuple[Note, ...] = (FirstSheetOnly(),) if item.mime_type == SPREADSHEET_MIME else ()
                return _text_content(data, extra)
            data = self._drive.download(item.id, MAX_DOWNLOAD_BYTES)
        except DownloadTooLarge:
            return ReadLimitation(LimitationReason.TOO_LARGE)
        except ExportTooLarge:
            return ReadLimitation(LimitationReason.EXPORT_TOO_LARGE)

        if kind is ContentKind.PDF:
            return read_pdf(data)
        if kind is ContentKind.IMAGE:
            prepared = prepare_image(data)
            if isinstance(prepared, ReadLimitation):
                return prepared
            part, notes = prepared
            return Content(parts=(part,), notes=notes)
        return _text_content(data, ())


def _text_content(data: bytes, extra: tuple[Note, ...]) -> Content:
    text, decode_notes = decode_text(data)
    text, truncated = truncate_text(text, MAX_TEXT_CHARS)
    notes = (*extra, *decode_notes, *((TextTruncated(limit_chars=MAX_TEXT_CHARS),) if truncated else ()))
    return Content(parts=(TextPart(text=text),), notes=notes)
