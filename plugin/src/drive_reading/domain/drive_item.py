"""Drive 上的一個項目（檔案、資料夾或捷徑）中，我們會用到的中繼資料。"""

from dataclasses import dataclass

FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"


@dataclass(frozen=True)
class DriveItem:
    id: str
    name: str
    mime_type: str
    # 現在的 Drive 一個項目只有一個 parent；沒有 parent 代表 My Drive 的根、共用雲端硬碟的根，
    # 或別人分享給我、但上層我看不到的項目
    parents: tuple[str, ...] = ()
    # 只有一般檔案有 size；Google 文件、試算表、資料夾沒有
    size: int | None = None
    modified_time: str | None = None
    # 項目在共用雲端硬碟中時才有值
    drive_id: str | None = None
    shortcut_target_id: str | None = None
    shortcut_target_mime_type: str | None = None

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME

    @property
    def is_shortcut(self) -> bool:
        return self.mime_type == SHORTCUT_MIME
