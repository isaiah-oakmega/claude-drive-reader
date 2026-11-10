"""list_files 的 use case：預設列出 Root Folder，指定資料夾時先通過 R1，結果交給 R3 的列出規則。"""

import pytest
from drive_fakes import ROOT_ID, FakeDrive, folder, sample_drive

from drive_reading.app import DriveReadingService, NotFoundOrNoAccess, OutsideRoot


def paths(result) -> list[str]:
    return [entry.path for entry in result.listing.entries]


def test_default_lists_whole_root_folder() -> None:
    result = DriveReadingService(sample_drive(), ROOT_ID).list_files()

    assert result.root.name == "Drive Reader 測試"
    assert result.folder.id == ROOT_ID
    assert result.folder_path == ()
    # 依路徑的字元順序排序（中文依 Unicode 碼位）
    assert paths(result) == ["readme.txt", "報告/", "報告/q1.pdf", "外部連結", "會議記錄"]


def test_subfolder_by_url_is_listed_with_its_path_from_root() -> None:
    result = DriveReadingService(sample_drive(), ROOT_ID).list_files(
        folder="https://drive.google.com/drive/folders/reports-id-0001?usp=sharing"
    )

    assert result.folder_path == ("報告",)
    assert paths(result) == ["q1.pdf"]


def test_non_recursive_lists_only_direct_children() -> None:
    drive = sample_drive()

    result = DriveReadingService(drive, ROOT_ID).list_files(recursive=False)

    assert "報告/q1.pdf" not in paths(result)
    assert drive.listed == [ROOT_ID]


def test_folder_outside_root_is_refused_without_listing_it() -> None:
    # 情境 13 的防線：就算 Claude 被誘導去列別的資料夾，也只會拿到 OUTSIDE_ROOT
    drive = sample_drive()

    with pytest.raises(OutsideRoot):
        DriveReadingService(drive, ROOT_ID).list_files(folder="outside-dir-01")
    assert drive.listed == []


def test_shortcut_target_outside_root_is_refused() -> None:
    # 捷徑在 Root Folder 內，但它指向的目標不在：R2 要求對目標套用 R1
    with pytest.raises(OutsideRoot):
        DriveReadingService(sample_drive(), ROOT_ID).list_files(folder="outside-file-01")


def test_unknown_folder_is_not_found() -> None:
    with pytest.raises(NotFoundOrNoAccess):
        DriveReadingService(sample_drive(), ROOT_ID).list_files(folder="does-not-exist-123")


def test_malformed_folder_parameter_is_not_found() -> None:
    with pytest.raises(NotFoundOrNoAccess):
        DriveReadingService(sample_drive(), ROOT_ID).list_files(folder="https://evil.example/folders/abcdefghijkl")


def test_inaccessible_root_folder_is_not_found() -> None:
    # 情境 11：用錯帳號，或還沒接受分享邀請
    drive = sample_drive()
    drive.hidden.add(ROOT_ID)

    with pytest.raises(NotFoundOrNoAccess) as raised:
        DriveReadingService(drive, ROOT_ID).list_files()
    assert raised.value.reference == ROOT_ID


def test_file_target_is_listed_as_single_entry() -> None:
    result = DriveReadingService(sample_drive(), ROOT_ID).list_files(folder="q1-id-000001")

    assert result.folder_path == ("報告", "q1.pdf")
    assert paths(result) == ["q1.pdf"]
    assert result.listing.truncated is False


def test_empty_folder_lists_nothing() -> None:
    drive = FakeDrive(folder(ROOT_ID, "my-drive", "空的"))

    assert paths(DriveReadingService(drive, ROOT_ID).list_files()) == []
