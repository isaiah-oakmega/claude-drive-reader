"""R1：Root Folder 是存取邊界。任何目標都必須能沿 parents 追溯到 Root Folder。

這是防範 prompt injection 的關鍵（情境 13）：檔案內容可能誘導 Claude 去讀別的檔案，
只要目標不在 Root Folder 底下，就一律拒絕，不管 Claude 被說服了什麼。
"""

from collections.abc import Callable

from drive_reading.domain.drive_item import DriveItem
from drive_reading.domain.errors import OutsideRoot
from drive_reading.domain.limits import MAX_ANCESTOR_DEPTH

# 查詢一個項目的中繼資料；沒有權限或不存在時回傳 None
Lookup = Callable[[str], DriveItem | None]


def path_from_root(item: DriveItem, root_id: str, lookup: Lookup) -> tuple[str, ...]:
    """回傳從 Root Folder 底下到 item 的名稱路徑（不含 Root Folder 本身）。不在子樹內就拋 OutsideRoot。"""
    if item.id == root_id:
        return ()
    names = [item.name]
    current = item
    for _ in range(MAX_ANCESTOR_DEPTH):
        if not current.parents:
            # 走到頂了還沒遇到 Root Folder
            raise OutsideRoot(item.id)
        parent_id = current.parents[0]
        if parent_id == root_id:
            return tuple(reversed(names))
        parent = lookup(parent_id)
        if parent is None:
            # 中間有一層看不到：無法證明它在 Root Folder 內，就當成在外面
            raise OutsideRoot(item.id)
        names.append(parent.name)
        current = parent
    # 超過 20 層：正常的資料夾不會這麼深，也可能是循環
    raise OutsideRoot(item.id)
