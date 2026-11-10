"""Drive Reading 對外公開的 API。mcp_server 只從這裡 import（依賴規則 1）。"""

from drive_reading.app.drive_reading_service import DriveReadingService, FileRead, FolderListing
from drive_reading.domain.drive_id import parse_drive_id
from drive_reading.domain.drive_item import DriveItem
from drive_reading.domain.errors import DriveReadingError, GoogleApiError, NotAFile, NotFoundOrNoAccess, OutsideRoot
from drive_reading.domain.listing import ListedEntry, Listing

__all__ = [
    "DriveItem",
    "DriveReadingError",
    "DriveReadingService",
    "FileRead",
    "FolderListing",
    "GoogleApiError",
    "ListedEntry",
    "Listing",
    "NotAFile",
    "NotFoundOrNoAccess",
    "OutsideRoot",
    "parse_drive_id",
]
