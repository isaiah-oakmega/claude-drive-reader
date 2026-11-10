"""Drive Reading 的 use case。階段 3 先有 list_files；read_file 在階段 4 加入。"""

from dataclasses import dataclass

from drive_reading.domain.drive_id import parse_drive_id
from drive_reading.domain.drive_item import DriveItem
from drive_reading.domain.listing import ListedEntry, Listing, build_listing
from drive_reading.domain.root_folder import path_from_root
from drive_reading.infra.drive_api import DriveApi


@dataclass(frozen=True)
class FolderListing:
    root: DriveItem
    folder: DriveItem
    # 從 Root Folder 底下到被列出項目的名稱路徑；列的是 Root Folder 本身時為空
    folder_path: tuple[str, ...]
    listing: Listing


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
