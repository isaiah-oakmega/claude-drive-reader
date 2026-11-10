"""R2 與 R3：列出子樹。深度最多 5 層、最多 500 筆、visited set 防止循環；捷徑不跟進，只標示目標。"""

from collections.abc import Iterator

from drive_reading.domain.drive_item import FOLDER_MIME, SHORTCUT_MIME, DriveItem
from drive_reading.domain.limits import MAX_LIST_DEPTH, MAX_LIST_ITEMS
from drive_reading.domain.listing import build_listing

ROOT = DriveItem(id="root", name="Root", mime_type=FOLDER_MIME)


def folder(item_id: str, name: str | None = None) -> DriveItem:
    return DriveItem(id=item_id, name=name or item_id, mime_type=FOLDER_MIME)


def file(item_id: str, name: str | None = None) -> DriveItem:
    return DriveItem(id=item_id, name=name or item_id, mime_type="text/plain", size=10)


class Children:
    """folder id → 子項目；記錄每個資料夾被展開幾次，以及實際讀了幾筆（確認截斷後不再往下讀）。"""

    def __init__(self, tree: dict[str, list[DriveItem]]) -> None:
        self.tree = tree
        self.expanded: list[str] = []
        self.yielded = 0

    def __call__(self, parent: DriveItem) -> Iterator[DriveItem]:
        self.expanded.append(parent.id)
        for item in self.tree.get(parent.id, []):
            self.yielded += 1
            yield item


def paths(listing) -> list[str]:
    return [entry.path for entry in listing.entries]


def test_recursive_listing_has_paths_relative_to_listed_folder() -> None:
    children = Children({"root": [folder("a", "報告"), file("f1", "readme.txt")], "a": [file("f2", "q1.pdf")]})

    listing = build_listing(ROOT, children, recursive=True)

    assert paths(listing) == ["readme.txt", "報告/", "報告/q1.pdf"]
    assert (listing.truncated, listing.unexpanded, listing.repeated) == (False, (), ())


def test_non_recursive_listing_does_not_expand_subfolders() -> None:
    children = Children({"root": [folder("a"), file("f1")], "a": [file("f2")]})

    listing = build_listing(ROOT, children, recursive=False)

    assert paths(listing) == ["a/", "f1"]
    assert children.expanded == ["root"]
    assert listing.unexpanded == ()


def test_shortcuts_are_listed_but_not_followed() -> None:
    shortcut = DriveItem(
        id="s", name="捷徑", mime_type=SHORTCUT_MIME, shortcut_target_id="target", shortcut_target_mime_type=FOLDER_MIME
    )
    children = Children({"root": [shortcut], "target": [file("inside-target")]})

    listing = build_listing(ROOT, children, recursive=True)

    assert [entry.item.shortcut_target_id for entry in listing.entries] == ["target"]
    assert children.expanded == ["root"]


def test_depth_is_limited_to_five_levels() -> None:
    assert MAX_LIST_DEPTH == 5
    tree = {"root": [folder("d1")]} | {f"d{i}": [folder(f"d{i + 1}")] for i in range(1, 8)}

    listing = build_listing(ROOT, Children(tree), recursive=True)

    assert paths(listing) == ["d1/", "d1/d2/", "d1/d2/d3/", "d1/d2/d3/d4/", "d1/d2/d3/d4/d5/"]
    assert listing.unexpanded == ("d1/d2/d3/d4/d5/",)


def test_item_count_is_capped_at_500_and_reading_stops() -> None:
    assert MAX_LIST_ITEMS == 500
    children = Children({"root": [file(f"f{i:04}") for i in range(MAX_LIST_ITEMS + 100)]})

    listing = build_listing(ROOT, children, recursive=True)

    assert len(listing.entries) == MAX_LIST_ITEMS
    assert listing.truncated is True
    # 第 501 筆讓我們知道還有更多，之後就不再向 Drive 要資料
    assert children.yielded == MAX_LIST_ITEMS + 1


def test_exactly_500_items_is_not_truncated() -> None:
    listing = build_listing(ROOT, Children({"root": [file(f"f{i:04}") for i in range(MAX_LIST_ITEMS)]}), recursive=True)

    assert (len(listing.entries), listing.truncated) == (MAX_LIST_ITEMS, False)


def test_shallow_items_are_kept_when_truncated() -> None:
    # 先列淺層再列深層：截斷時保留的是最上層的全貌，而不是某個角落的細節
    tree = {"root": [folder("a"), *[file(f"top{i:03}") for i in range(MAX_LIST_ITEMS - 1)]], "a": [file("deep")]}

    listing = build_listing(ROOT, Children(tree), recursive=True)

    assert "a/deep" not in paths(listing)
    assert listing.truncated is True


def test_folder_seen_twice_is_listed_but_expanded_once() -> None:
    # 舊版 Drive 允許一個資料夾有多個 parent，可能形成循環
    loop = folder("a")
    children = Children({"root": [loop], "a": [folder("b")], "b": [loop]})

    listing = build_listing(ROOT, children, recursive=True)

    assert paths(listing) == ["a/", "a/b/", "a/b/a/"]
    assert children.expanded == ["root", "a", "b"]
    assert listing.repeated == ("a/b/a/",)


def test_output_is_sorted_by_path() -> None:
    children = Children({"root": [file("z"), folder("m"), file("a")], "m": [file("b")]})

    assert paths(build_listing(ROOT, children, recursive=True)) == ["a", "m/", "m/b", "z"]
