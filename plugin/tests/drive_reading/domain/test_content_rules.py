"""R4、R4a、R5 的純規則：類型分派、文字上限、PDF 逐頁決定文字或影像。"""

import pytest

from drive_reading.domain.content_kind import ContentKind, classify, export_format
from drive_reading.domain.limits import (
    MAX_RENDERED_PAGES,
    MAX_TEXT_CHARS,
    MAX_TEXT_CHARS_WITH_IMAGES,
    MIN_TEXT_CHARS_PER_PAGE,
)
from drive_reading.domain.outcomes import (
    ImagePart,
    NoTextLayer,
    PagesOmitted,
    PagesRendered,
    TextPart,
    TextTruncated,
)
from drive_reading.domain.pdf_layout import assemble_pdf
from drive_reading.domain.text import truncate_text

# ---------- 類型分派 ----------


@pytest.mark.parametrize(
    "mime, kind",
    [
        ("application/vnd.google-apps.document", ContentKind.GOOGLE_EXPORT),
        ("application/vnd.google-apps.spreadsheet", ContentKind.GOOGLE_EXPORT),
        ("application/vnd.google-apps.presentation", ContentKind.GOOGLE_EXPORT),
        ("application/vnd.google-apps.form", ContentKind.UNSUPPORTED),
        ("application/vnd.google-apps.drawing", ContentKind.UNSUPPORTED),
        ("application/pdf", ContentKind.PDF),
        ("image/png", ContentKind.IMAGE),
        ("image/jpeg", ContentKind.IMAGE),
        ("image/heic", ContentKind.IMAGE),
        ("image/svg+xml", ContentKind.TEXT),
        ("text/plain", ContentKind.TEXT),
        ("text/csv", ContentKind.TEXT),
        ("text/markdown", ContentKind.TEXT),
        ("application/json", ContentKind.TEXT),
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ContentKind.UNSUPPORTED),
        ("application/zip", ContentKind.UNSUPPORTED),
        ("video/mp4", ContentKind.UNSUPPORTED),
    ],
)
def test_mime_types_map_to_handling(mime: str, kind: ContentKind) -> None:
    assert classify(mime) is kind


def test_google_formats_export_per_c4() -> None:
    assert export_format("application/vnd.google-apps.document") == "text/markdown"
    assert export_format("application/vnd.google-apps.spreadsheet") == "text/csv"
    assert export_format("application/vnd.google-apps.presentation") == "text/plain"


# ---------- 文字上限 ----------


def test_text_under_limit_is_untouched() -> None:
    assert truncate_text("abc", 10) == ("abc", False)


def test_text_over_limit_is_cut_and_flagged() -> None:
    assert MAX_TEXT_CHARS == 50_000
    text, truncated = truncate_text("字" * (MAX_TEXT_CHARS + 5), MAX_TEXT_CHARS)

    assert (len(text), truncated) == (MAX_TEXT_CHARS, True)


# ---------- R4a：PDF 逐頁 ----------


class FakePdf:
    """pages：每頁抽出的文字。render 回傳假的影像並記錄算繪了哪幾頁（0 起算）。"""

    def __init__(self, pages: list[str]) -> None:
        self.pages = pages
        self.rendered: list[int] = []

    def text(self, index: int) -> str:
        return self.pages[index]

    def render(self, index: int) -> ImagePart:
        self.rendered.append(index)
        return ImagePart(data=b"png", mime_type="image/png", width=100, height=140, page=index + 1)

    def assemble(self):
        return assemble_pdf(len(self.pages), self.text, self.render)


TEXT_PAGE = "這一頁有足夠的文字層內容，可以直接抽出文字。" * 2
SCANNED = "  \n "


def kinds(content) -> list[str]:
    return [f"{'T' if isinstance(part, TextPart) else 'I'}{part.page}" for part in content.parts]


def test_text_pdf_returns_text_per_page_in_order() -> None:
    pdf = FakePdf([TEXT_PAGE, TEXT_PAGE, TEXT_PAGE])

    content = pdf.assemble()

    assert kinds(content) == ["T1", "T2", "T3"]
    assert pdf.rendered == []
    assert content.notes == ()


def test_scanned_pdf_renders_first_five_pages_and_says_no_text_layer() -> None:
    assert MAX_RENDERED_PAGES == 5
    pdf = FakePdf([SCANNED] * 8)

    content = pdf.assemble()

    assert kinds(content) == ["I1", "I2", "I3", "I4", "I5"]
    assert NoTextLayer() in content.notes
    assert PagesOmitted(from_page=6, total_pages=8) in content.notes


def test_mixed_pdf_interleaves_text_and_images_by_page_number() -> None:
    pdf = FakePdf([TEXT_PAGE, SCANNED, TEXT_PAGE, SCANNED])

    content = pdf.assemble()

    assert kinds(content) == ["T1", "I2", "T3", "I4"]
    assert PagesRendered(pages=(2, 4)) in content.notes
    assert NoTextLayer() not in content.notes


def test_page_below_text_threshold_is_rendered() -> None:
    assert MIN_TEXT_CHARS_PER_PAGE == 20
    # 頁碼、頁首之類的零星文字不算文字層
    pdf = FakePdf(["第 1 頁　　　　 - 12 -", "a" * MIN_TEXT_CHARS_PER_PAGE])

    assert kinds(pdf.assemble()) == ["I1", "T2"]


def test_text_beyond_limit_is_truncated_and_later_pages_omitted() -> None:
    page = "x" * 20_000
    pdf = FakePdf([page, page, page, page])

    content = pdf.assemble()

    assert sum(len(part.text) for part in content.parts) == MAX_TEXT_CHARS
    assert kinds(content) == ["T1", "T2", "T3"]
    assert TextTruncated(limit_chars=MAX_TEXT_CHARS) in content.notes
    assert PagesOmitted(from_page=4, total_pages=4) in content.notes


def test_text_budget_is_smaller_once_images_are_included() -> None:
    # 含影像的結果整體要在 Claude Code 的 25,000 token 上限內，文字預算因此降到 10,000 字
    assert MAX_TEXT_CHARS_WITH_IMAGES == 10_000
    pdf = FakePdf([SCANNED, "y" * 8_000, "y" * 8_000, TEXT_PAGE])

    content = pdf.assemble()

    assert sum(len(part.text) for part in content.parts if isinstance(part, TextPart)) == MAX_TEXT_CHARS_WITH_IMAGES
    assert TextTruncated(limit_chars=MAX_TEXT_CHARS_WITH_IMAGES) in content.notes
    assert PagesOmitted(from_page=4, total_pages=4) in content.notes


def test_scanned_page_after_long_text_stops_the_output() -> None:
    # 已經有超過 10,000 字的文字，再加影像就會超過整體上限：從這一頁開始省略
    pdf = FakePdf(["z" * 30_000, SCANNED, TEXT_PAGE])

    content = pdf.assemble()

    assert kinds(content) == ["T1"]
    assert pdf.rendered == []
    assert PagesOmitted(from_page=2, total_pages=3) in content.notes


def test_truncation_on_last_page_does_not_claim_omitted_pages() -> None:
    content = FakePdf(["w" * (MAX_TEXT_CHARS + 10)]).assemble()

    assert TextTruncated(limit_chars=MAX_TEXT_CHARS) in content.notes
    assert not any(isinstance(note, PagesOmitted) for note in content.notes)


def test_empty_pdf_has_no_parts() -> None:
    assert FakePdf([]).assemble().parts == ()
