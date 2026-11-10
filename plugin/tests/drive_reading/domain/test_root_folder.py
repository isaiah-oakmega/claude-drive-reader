"""R1：目標必須在 Root Folder 子樹內。沿 parents 往上追溯，遇到 Root Folder 才放行；最多 20 層。"""

import pytest

from drive_reading.domain.drive_item import FOLDER_MIME, DriveItem
from drive_reading.domain.errors import OutsideRoot
from drive_reading.domain.limits import MAX_ANCESTOR_DEPTH
from drive_reading.domain.root_folder import path_from_root

ROOT = "root-folder-id"


def folder(item_id: str, parent: str | None, name: str | None = None) -> DriveItem:
    return DriveItem(id=item_id, name=name or item_id, mime_type=FOLDER_MIME, parents=(parent,) if parent else ())


class Tree:
    """記憶體裡的一棵樹。lookup 對「無法存取」的項目回傳 None，就像 Drive 回 404。"""

    def __init__(self, *items: DriveItem, hidden: set[str] = frozenset()) -> None:
        self.items = {item.id: item for item in items}
        self.hidden = hidden
        self.lookups: list[str] = []

    def lookup(self, item_id: str) -> DriveItem | None:
        self.lookups.append(item_id)
        return None if item_id in self.hidden else self.items.get(item_id)


def chain(depth: int) -> tuple[Tree, DriveItem]:
    """ROOT → d1 → d2 → … → d<depth>，回傳最深的那一個。"""
    items = [folder("d1", ROOT)] + [folder(f"d{i}", f"d{i - 1}") for i in range(2, depth + 1)]
    return Tree(folder(ROOT, "my-drive", "Root"), *items), items[-1]


def test_root_itself_is_inside() -> None:
    assert path_from_root(folder(ROOT, "my-drive"), ROOT, Tree().lookup) == ()


def test_direct_child_is_inside_without_any_lookup() -> None:
    tree = Tree()

    assert path_from_root(folder("a", ROOT, "報告"), ROOT, tree.lookup) == ("報告",)
    assert tree.lookups == []


def test_nested_item_returns_path_below_root() -> None:
    tree = Tree(folder("a", ROOT, "2026"), folder("b", "a", "Q1"))
    item = DriveItem(id="c", name="memo.pdf", mime_type="application/pdf", parents=("b",))

    assert path_from_root(item, ROOT, tree.lookup) == ("2026", "Q1", "memo.pdf")


def test_twenty_levels_is_the_limit() -> None:
    assert MAX_ANCESTOR_DEPTH == 20
    tree, deepest = chain(MAX_ANCESTOR_DEPTH)
    assert len(path_from_root(deepest, ROOT, tree.lookup)) == MAX_ANCESTOR_DEPTH

    tree, deeper = chain(MAX_ANCESTOR_DEPTH + 1)
    with pytest.raises(OutsideRoot):
        path_from_root(deeper, ROOT, tree.lookup)


def test_item_elsewhere_in_my_drive_is_outside() -> None:
    tree = Tree(folder("other", "my-drive"), folder("my-drive", None, "My Drive"))

    with pytest.raises(OutsideRoot):
        path_from_root(folder("x", "other"), ROOT, tree.lookup)


def test_item_without_parents_is_outside() -> None:
    # 沒有 parents：My Drive 的根、共用雲端硬碟的根，或別人分享給我但上層我看不到的項目
    with pytest.raises(OutsideRoot):
        path_from_root(folder("orphan", None), ROOT, Tree().lookup)


def test_inaccessible_ancestor_is_outside() -> None:
    # 中間有一層我沒有權限：無法證明它在 Root Folder 內，就當成在外面
    tree = Tree(folder("secret", ROOT), folder("a", "secret"), hidden={"secret"})

    with pytest.raises(OutsideRoot):
        path_from_root(folder("b", "a"), ROOT, tree.lookup)


def test_shared_drive_item_reaches_root_inside_the_same_shared_drive() -> None:
    # 共用雲端硬碟中的項目同樣有 parents，一路追到 Root Folder 就放行
    shared_root = DriveItem(id=ROOT, name="Root", mime_type=FOLDER_MIME, parents=("shared-drive-id",), drive_id="shared-drive-id")
    tree = Tree(shared_root, DriveItem(id="a", name="a", mime_type=FOLDER_MIME, parents=(ROOT,), drive_id="shared-drive-id"))
    item = DriveItem(id="b", name="b.txt", mime_type="text/plain", parents=("a",), drive_id="shared-drive-id")

    assert path_from_root(item, ROOT, tree.lookup) == ("a", "b.txt")


def test_shared_drive_root_without_reaching_root_folder_is_outside() -> None:
    tree = Tree(DriveItem(id="shared-drive-id", name="Team", mime_type=FOLDER_MIME, drive_id="shared-drive-id"))
    item = DriveItem(id="b", name="b.txt", mime_type="text/plain", parents=("shared-drive-id",), drive_id="shared-drive-id")

    with pytest.raises(OutsideRoot):
        path_from_root(item, ROOT, tree.lookup)


def test_parent_cycle_does_not_loop_forever() -> None:
    tree = Tree(folder("a", "b"), folder("b", "a"))

    with pytest.raises(OutsideRoot):
        path_from_root(folder("c", "a"), ROOT, tree.lookup)
    assert len(tree.lookups) <= MAX_ANCESTOR_DEPTH
