"""PDF：用 pypdfium2 逐頁抽文字、只在需要時算繪頁面（R4a）。哪一頁用文字或影像由 domain/pdf_layout.py 決定。"""

import threading

import pypdfium2 as pdfium

from drive_reading.domain.limits import MAX_IMAGE_SIDE
from drive_reading.domain.outcomes import Content, ImagePart, LimitationReason, ReadLimitation
from drive_reading.domain.pdf_layout import assemble_pdf
from drive_reading.infra.content.image import encode_image

# PDFium 不是 thread-safe，而 MCP 的 tool 在 worker thread 執行，兩個 read_file 可能同時進來。
# 同一時間只讓一份 PDF 使用 PDFium。
_PDFIUM_LOCK = threading.Lock()


def read_pdf(data: bytes) -> Content | ReadLimitation:
    with _PDFIUM_LOCK:
        try:
            document = pdfium.PdfDocument(data)
        except pdfium.PdfiumError as error:
            if getattr(error, "err_code", None) == pdfium.raw.FPDF_ERR_PASSWORD:
                return ReadLimitation(LimitationReason.PASSWORD_PROTECTED)
            return ReadLimitation(LimitationReason.DAMAGED)
        try:
            return assemble_pdf(len(document), lambda index: _page_text(document, index), lambda index: _render(document, index))
        except pdfium.PdfiumError:
            # 文件能開啟，但某一頁壞掉
            return ReadLimitation(LimitationReason.DAMAGED)
        finally:
            document.close()


def _page_text(document: pdfium.PdfDocument, index: int) -> str:
    page = document[index]
    try:
        text_page = page.get_textpage()
        try:
            return text_page.get_text_range()
        finally:
            text_page.close()
    finally:
        page.close()


def _render(document: pdfium.PdfDocument, index: int) -> ImagePart:
    page = document[index]
    try:
        width, height = page.get_size()
        # PDF 的單位是 point（1/72 英吋）；把長邊放大或縮小到剛好 1568px，掃描頁上的字才看得清楚
        bitmap = page.render(scale=MAX_IMAGE_SIDE / max(width, height))
        try:
            return encode_image(bitmap.to_pil(), page=index + 1)
        finally:
            bitmap.close()
    finally:
        page.close()
