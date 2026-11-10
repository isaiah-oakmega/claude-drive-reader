"""read_file 的 use case：R1、R2 先檢查範圍，再依類型取得內容，所有上限都回成 Read Limitation（R5）。"""

import pytest
from drive_fakes import ROOT_ID, FakeDrive, file, folder, shortcut
from pdf_builder import build_pdf, image_page, text_page

from drive_reading.app import DriveItem, DriveReadingService, NotAFile, NotFoundOrNoAccess, OutsideRoot
from drive_reading.domain.limits import MAX_DOWNLOAD_BYTES, MAX_TEXT_CHARS
from drive_reading.domain.outcomes import (
    Content,
    FirstSheetOnly,
    ImagePart,
    LimitationReason,
    NoTextLayer,
    ReadLimitation,
    TextPart,
    TextTruncated,
)

DOC_MIME = "application/vnd.google-apps.document"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
SLIDES_MIME = "application/vnd.google-apps.presentation"


def native(item_id: str, mime: str, name: str) -> DriveItem:
    return DriveItem(id=item_id, name=name, mime_type=mime, parents=(ROOT_ID,), modified_time="2026-11-01T10:00:00.000Z")


@pytest.fixture
def drive() -> FakeDrive:
    drive = FakeDrive(
        folder(ROOT_ID, "my-drive", "Root"),
        folder("sub-id-000001", ROOT_ID, "子資料夾"),
        file("text-pdf-0001", "sub-id-000001", "report.pdf"),
        file("scan-pdf-0001", ROOT_ID, "scan.pdf"),
        file("notes-txt-001", ROOT_ID, "notes.txt", mime="text/plain"),
        file("photo-png-001", ROOT_ID, "photo.png", mime="image/png"),
        file("archive-zip-1", ROOT_ID, "archive.zip", mime="application/zip"),
        file("huge-pdf-0001", ROOT_ID, "huge.pdf", size=MAX_DOWNLOAD_BYTES + 1),
        native("doc-id-000001", DOC_MIME, "會議記錄"),
        native("sheet-id-0001", SHEET_MIME, "預算"),
        native("slides-id-001", SLIDES_MIME, "簡報"),
        shortcut("link-in-00001", ROOT_ID, "text-pdf-0001", name="報告捷徑"),
        shortcut("link-out-0001", ROOT_ID, "outside-file-01", name="外部捷徑"),
        folder("outside-dir-01", "my-drive", "別人的"),
        file("outside-file-01", "outside-dir-01", "secret.pdf"),
        folder("my-drive", None, "My Drive"),
    )
    drive.contents |= {
        "text-pdf-0001": build_pdf(text_page("Annual report text layer with plenty of characters.")),
        "scan-pdf-0001": build_pdf(image_page(), image_page()),
        "notes-txt-001": "筆記內容".encode(),
        "photo-png-001": _png(),
        "outside-file-01": build_pdf(text_page("Secret text that must never be read by Drive Reader.")),
    }
    drive.exports |= {
        ("doc-id-000001", "text/markdown"): "# 會議記錄\n- 決議一".encode(),
        ("sheet-id-0001", "text/csv"): "項目,金額\n午餐,100".encode(),
        ("slides-id-001", "text/plain"): "第一張投影片".encode(),
    }
    return drive


def _png() -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), (10, 120, 200)).save(buffer, "PNG")
    return buffer.getvalue()


def read(drive: FakeDrive, reference: str):
    return DriveReadingService(drive, ROOT_ID).read_file(reference)


# ---------- 範圍：R1、R2 ----------


def test_file_in_subfolder_is_read_with_its_path(drive: FakeDrive) -> None:
    result = read(drive, "https://drive.google.com/file/d/text-pdf-0001/view")

    assert result.path == ("子資料夾", "report.pdf")
    assert isinstance(result.outcome, Content)
    assert "Annual report" in result.outcome.parts[0].text


def test_file_outside_root_is_refused_before_download(drive: FakeDrive) -> None:
    # 情境 13：不管 Claude 被誘導去讀什麼，範圍外的檔案連下載都不會發生
    with pytest.raises(OutsideRoot):
        read(drive, "outside-file-01")
    assert drive.downloaded == []


def test_shortcut_inside_root_is_followed_to_its_target(drive: FakeDrive) -> None:
    result = read(drive, "link-in-00001")

    assert result.shortcut.name == "報告捷徑"
    assert result.item.id == "text-pdf-0001"
    assert isinstance(result.outcome, Content)


def test_shortcut_to_outside_target_is_refused(drive: FakeDrive) -> None:
    # R2：捷徑本身在 Root Folder 內不夠，目標也必須在
    with pytest.raises(OutsideRoot):
        read(drive, "link-out-0001")
    assert drive.downloaded == []


def test_folder_is_not_a_file(drive: FakeDrive) -> None:
    with pytest.raises(NotAFile):
        read(drive, "sub-id-000001")
    with pytest.raises(NotAFile):
        read(drive, ROOT_ID)


def test_missing_file_is_not_found(drive: FakeDrive) -> None:
    with pytest.raises(NotFoundOrNoAccess):
        read(drive, "missing-file-1")


# ---------- 依類型處理 ----------


def test_scanned_pdf_returns_page_images(drive: FakeDrive) -> None:
    outcome = read(drive, "scan-pdf-0001").outcome

    assert all(isinstance(part, ImagePart) for part in outcome.parts)
    assert NoTextLayer() in outcome.notes


def test_image_is_returned_as_image(drive: FakeDrive) -> None:
    (part,) = read(drive, "photo-png-001").outcome.parts

    assert isinstance(part, ImagePart)
    assert (part.width, part.height) == (64, 48)


def test_text_file_is_returned_as_text(drive: FakeDrive) -> None:
    assert read(drive, "notes-txt-001").outcome == Content(parts=(TextPart(text="筆記內容"),))


@pytest.mark.parametrize(
    "item_id, expected, notes",
    [
        ("doc-id-000001", "# 會議記錄\n- 決議一", ()),
        ("sheet-id-0001", "項目,金額\n午餐,100", (FirstSheetOnly(),)),
        ("slides-id-001", "第一張投影片", ()),
    ],
    ids=["doc-markdown", "sheet-csv", "slides-text"],
)
def test_google_formats_are_exported(drive: FakeDrive, item_id: str, expected: str, notes: tuple) -> None:
    # 情境 9：試算表要註明只有第一個工作表
    assert read(drive, item_id).outcome == Content(parts=(TextPart(text=expected),), notes=notes)


def test_long_text_is_truncated(drive: FakeDrive) -> None:
    drive.contents["notes-txt-001"] = ("字" * (MAX_TEXT_CHARS + 1)).encode()

    outcome = read(drive, "notes-txt-001").outcome

    assert len(outcome.parts[0].text) == MAX_TEXT_CHARS
    assert TextTruncated(limit_chars=MAX_TEXT_CHARS) in outcome.notes


# ---------- R5：Read Limitation，不下載或中止下載 ----------


def test_unsupported_type_is_not_downloaded(drive: FakeDrive) -> None:
    # 情境 10
    assert read(drive, "archive-zip-1").outcome == ReadLimitation(LimitationReason.UNSUPPORTED_TYPE)
    assert drive.downloaded == []


def test_file_known_to_be_too_large_is_not_downloaded(drive: FakeDrive) -> None:
    assert read(drive, "huge-pdf-0001").outcome == ReadLimitation(LimitationReason.TOO_LARGE)
    assert drive.downloaded == []


def test_export_over_limit_is_too_large(drive: FakeDrive) -> None:
    # Google 原生文件沒有 size，只能在下載中發現太大
    drive.exports[("doc-id-000001", "text/markdown")] = b"x" * (MAX_DOWNLOAD_BYTES + 1)

    assert read(drive, "doc-id-000001").outcome == ReadLimitation(LimitationReason.TOO_LARGE)


def test_google_export_size_limit_is_a_read_limitation(drive: FakeDrive) -> None:
    drive.export_too_large.add("doc-id-000001")

    assert read(drive, "doc-id-000001").outcome == ReadLimitation(LimitationReason.EXPORT_TOO_LARGE)


def test_unreadable_pdf_is_a_read_limitation(drive: FakeDrive) -> None:
    drive.contents["scan-pdf-0001"] = b"%PDF-1.4 broken"

    assert read(drive, "scan-pdf-0001").outcome == ReadLimitation(LimitationReason.DAMAGED)
