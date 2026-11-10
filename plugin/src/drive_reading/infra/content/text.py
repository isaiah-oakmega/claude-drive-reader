"""文字檔：解碼成字串（實作規格「SVG 與文字類型以 UTF-8 文字回傳」）。"""

import codecs

from drive_reading.domain.outcomes import Note, UndecodableCharacters


def decode_text(data: bytes) -> tuple[str, tuple[Note, ...]]:
    # 有 BOM 時以 BOM 為準：Windows 的記事本常存成 UTF-16 或帶 BOM 的 UTF-8
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16"), ()
    try:
        return data.decode("utf-8-sig"), ()
    except UnicodeDecodeError:
        # 例如 Big5 的舊檔案。不去猜編碼（猜錯會變成看似正常的亂碼），
        # 用替代字元標出無法解碼的位置，並在回傳時註明
        return data.decode("utf-8", errors="replace"), (UndecodableCharacters(),)
