"""內容處理的 infra：PDF（pypdfium2）、圖片（Pillow）、文字解碼。用真的函式庫處理測試產生的檔案。"""

import io

import pytest
from PIL import Image
from pdf_builder import build_pdf, image_page, text_page

from drive_reading.domain.limits import MAX_IMAGE_SIDE
from drive_reading.domain.outcomes import (
    FirstFrameOnly,
    ImagePart,
    ImageResized,
    LimitationReason,
    NoTextLayer,
    PagesRendered,
    ReadLimitation,
    TextPart,
    UndecodableCharacters,
)
from drive_reading.infra.content import image as image_content
from drive_reading.infra.content import pdf as pdf_content
from drive_reading.infra.content.text import decode_text

SENTENCE = "Quarterly report: revenue grew twelve percent compared with last year."


def png(width: int, height: int, mode: str = "RGB", color=(200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new(mode, (width, height), color if mode == "RGB" else (*color, 128)).save(buffer, "PNG")
    return buffer.getvalue()


def opened(part: ImagePart) -> Image.Image:
    image = Image.open(io.BytesIO(part.data))
    assert image.format == {"image/png": "PNG", "image/jpeg": "JPEG"}[part.mime_type]
    assert image.size == (part.width, part.height)
    return image


# ---------- PDF ----------


def test_text_pdf_is_read_as_text() -> None:
    content = pdf_content.read_pdf(build_pdf(text_page(SENTENCE), text_page("Second page has its own words too.")))

    assert [type(part) for part in content.parts] == [TextPart, TextPart]
    assert SENTENCE in content.parts[0].text
    assert [part.page for part in content.parts] == [1, 2]


def test_scanned_pdf_pages_are_rendered_within_size_limit() -> None:
    content = pdf_content.read_pdf(build_pdf(image_page(), image_page()))

    assert [type(part) for part in content.parts] == [ImagePart, ImagePart]
    for part in content.parts:
        image = opened(part)
        assert max(image.size) == MAX_IMAGE_SIDE
    assert NoTextLayer() in content.notes


def test_mixed_pdf_keeps_page_order() -> None:
    content = pdf_content.read_pdf(build_pdf(text_page(SENTENCE), image_page(), text_page(SENTENCE)))

    assert [(type(part).__name__, part.page) for part in content.parts] == [("TextPart", 1), ("ImagePart", 2), ("TextPart", 3)]
    assert PagesRendered(pages=(2,)) in content.notes


def test_damaged_pdf_is_a_read_limitation() -> None:
    assert pdf_content.read_pdf(b"%PDF-1.4 this is not really a pdf") == ReadLimitation(LimitationReason.DAMAGED)


def test_password_protected_pdf_is_a_read_limitation(monkeypatch: pytest.MonkeyPatch) -> None:
    # 手寫加密 PDF 太複雜；改為模擬 pdfium 回報「需要密碼」的錯誤代碼
    import pypdfium2

    def needs_password(*args, **kwargs):
        error = pypdfium2.PdfiumError("Failed to load document (PDFium: Incorrect password error).")
        error.err_code = pypdfium2.raw.FPDF_ERR_PASSWORD
        raise error

    monkeypatch.setattr(pdf_content.pdfium, "PdfDocument", needs_password)

    assert pdf_content.read_pdf(b"%PDF-") == ReadLimitation(LimitationReason.PASSWORD_PROTECTED)


# ---------- 圖片 ----------


def test_large_image_is_shrunk_to_long_side_limit() -> None:
    part, notes = image_content.prepare_image(png(3000, 2000))

    image = opened(part)
    assert image.size == (MAX_IMAGE_SIDE, 1045)
    assert ImageResized(original_width=3000, original_height=2000) in notes


def test_small_image_keeps_its_size() -> None:
    part, notes = image_content.prepare_image(png(400, 300))

    assert (part.width, part.height) == (400, 300)
    assert notes == ()


def test_opaque_image_is_sent_as_jpeg_and_transparent_as_png() -> None:
    opaque, _ = image_content.prepare_image(png(50, 50))
    transparent, _ = image_content.prepare_image(png(50, 50, mode="RGBA"))

    assert opaque.mime_type == "image/jpeg"
    assert transparent.mime_type == "image/png"
    assert opened(transparent).mode == "RGBA"


def test_animated_gif_uses_first_frame() -> None:
    buffer = io.BytesIO()
    frames = [Image.new("RGB", (40, 40), color) for color in ((255, 0, 0), (0, 255, 0))]
    frames[0].save(buffer, "GIF", save_all=True, append_images=frames[1:])

    part, notes = image_content.prepare_image(buffer.getvalue())

    assert opened(part).convert("RGB").getpixel((20, 20))[0] > 200
    assert FirstFrameOnly() in notes


def test_unknown_image_format_is_a_read_limitation() -> None:
    # 例如 HEIC：Pillow 沒有內建支援
    assert image_content.prepare_image(b"\x00\x00\x00\x18ftypheic....") == ReadLimitation(LimitationReason.IMAGE_FORMAT_UNSUPPORTED)


def test_truncated_image_is_damaged() -> None:
    assert image_content.prepare_image(png(500, 500)[:200]) == ReadLimitation(LimitationReason.DAMAGED)


def test_decompression_bomb_is_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    # 檔案很小但解壓後像素極多的圖片，會吃光記憶體；Pillow 偵測到時當成「太大」
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)

    assert image_content.prepare_image(png(100, 100)) == ReadLimitation(LimitationReason.TOO_LARGE)


# ---------- 文字 ----------


@pytest.mark.parametrize(
    "data",
    ["中文與 English".encode("utf-8"), "﻿中文與 English".encode("utf-8"), "中文與 English".encode("utf-16")],
    ids=["utf-8", "utf-8-bom", "utf-16-bom"],
)
def test_text_is_decoded(data: bytes) -> None:
    assert decode_text(data) == ("中文與 English", ())


def test_non_utf8_text_is_decoded_with_replacement_and_noted() -> None:
    text, notes = decode_text("中文".encode("big5") + b" ok")

    assert text.endswith(" ok")
    assert UndecodableCharacters() in notes
