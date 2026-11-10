"""R2、R3：列出一個資料夾的子樹。"""

from collections import deque
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from drive_reading.domain.drive_item import DriveItem
from drive_reading.domain.limits import MAX_LIST_DEPTH, MAX_LIST_ITEMS

# 回傳一個資料夾的直接子項目。可以是逐頁向 Drive 要資料的 generator：截斷時就不再往下要。
Children = Callable[[DriveItem], Iterable[DriveItem]]


@dataclass(frozen=True)
class ListedEntry:
    # 相對於被列出的資料夾；資料夾以 "/" 結尾，一眼就能和檔案區分
    path: str
    item: DriveItem


@dataclass(frozen=True)
class Listing:
    entries: tuple[ListedEntry, ...]
    # 超過 500 筆，後面的項目沒有列出
    truncated: bool
    # 位在第 5 層、沒有再往下展開的資料夾
    unexpanded: tuple[str, ...]
    # 已經展開過、這次跳過的資料夾（多個 parent 造成的循環）
    repeated: tuple[str, ...]


def build_listing(folder: DriveItem, children: Children, recursive: bool) -> Listing:
    entries: list[ListedEntry] = []
    unexpanded: list[str] = []
    repeated: list[str] = []
    visited = {folder.id}
    # 廣度優先：先列完淺層再往深處走，超過 500 筆被截斷時，保留的是上層的全貌
    pending: deque[tuple[DriveItem, str, int]] = deque([(folder, "", 1)])
    truncated = False

    while pending and not truncated:
        current, prefix, depth = pending.popleft()
        for child in children(current):
            if len(entries) == MAX_LIST_ITEMS:
                # 看到第 501 筆才知道真的還有更多；之後不再向 Drive 要任何資料
                truncated = True
                break
            path = f"{prefix}{child.name}/" if child.is_folder else f"{prefix}{child.name}"
            entries.append(ListedEntry(path=path, item=child))
            # R2：捷徑不是資料夾，不會被展開，只在輸出中標示目標
            if not (recursive and child.is_folder):
                continue
            if child.id in visited:
                repeated.append(path)
            elif depth >= MAX_LIST_DEPTH:
                unexpanded.append(path)
            else:
                visited.add(child.id)
                pending.append((child, path, depth + 1))

    return Listing(
        entries=tuple(sorted(entries, key=lambda entry: entry.path)),
        truncated=truncated,
        unexpanded=tuple(unexpanded),
        repeated=tuple(repeated),
    )
