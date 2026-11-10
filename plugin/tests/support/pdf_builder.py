"""測試用的最小 PDF 產生器：每一頁是一段文字（有文字層），或一張影像（沒有文字層，像掃描頁）。

不用待測的 pypdfium2 來產生測試檔，避免「用同一個函式庫寫、再用它讀」而看不出問題。
PDF 的結構照 ISO 32000：物件、xref 位移表、trailer。文字只用 ASCII 與內建的 Helvetica 字型。
"""

import zlib

PAGE_WIDTH, PAGE_HEIGHT = 595, 842  # A4，單位是 point（1/72 英吋）


def text_page(*lines: str) -> str:
    return "\n".join(lines)


def image_page(width: int = 60, height: int = 80, color: tuple[int, int, int] = (40, 90, 160)) -> tuple[int, int, bytes]:
    return (width, height, bytes(color) * (width * height))


def build_pdf(*pages: str | tuple[int, int, bytes]) -> bytes:
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # 先佔位，等 pages 的編號確定後再填
    pages_obj = add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_ids = []
    for page in pages:
        if isinstance(page, str):
            content = _text_stream(page)
            resources = f"<< /Font << /F1 {font} 0 R >> >>".encode()
        else:
            width, height, rgb = page
            data = zlib.compress(rgb)
            image = add(
                f"<< /Type /XObject /Subtype /Image /Width {width} /Height {height} /ColorSpace /DeviceRGB "
                f"/BitsPerComponent 8 /Filter /FlateDecode /Length {len(data)} >>\nstream\n".encode()
                + data
                + b"\nendstream"
            )
            content = f"q {PAGE_WIDTH} 0 0 {PAGE_HEIGHT} 0 0 cm /Im1 Do Q".encode()
            resources = f"<< /XObject << /Im1 {image} 0 R >> >>".encode()
        stream = add(f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream")
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Contents {stream} 0 R /Resources ".encode()
                + resources
                + b" >>"
            )
        )
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_obj - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _text_stream(text: str) -> bytes:
    commands = ["BT", "/F1 12 Tf", "50 790 Td"]
    for line in text.split("\n"):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        commands += [f"({escaped}) Tj", "0 -16 Td"]
    commands.append("ET")
    return "\n".join(commands).encode("ascii")
