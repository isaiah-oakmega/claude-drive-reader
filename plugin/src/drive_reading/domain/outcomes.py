"""R5：讀取的結果只有兩種，都是正常結果，不是例外。

- Content：交付了內容，可能附帶註記（截斷、省略頁數、無文字層……），這些註記也是 Read Limitation。
- ReadLimitation：完全無法交付內容（不支援、太大、有密碼……），附上原因。

這裡只描述發生了什麼；給 Claude 看的文字由 mcp_server 決定。
"""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class TextPart:
    text: str
    # PDF 的頁碼（1 起算）；不是 PDF 時為 None
    page: int | None = None


@dataclass(frozen=True)
class ImagePart:
    data: bytes
    # 只會是 image/png 或 image/jpeg
    mime_type: str
    width: int
    height: int
    page: int | None = None


# ---------- 註記：內容交付了，但不是完整的原樣 ----------


@dataclass(frozen=True)
class TextTruncated:
    limit_chars: int


@dataclass(frozen=True)
class PagesOmitted:
    # 從第幾頁開始沒有回傳（1 起算）
    from_page: int
    total_pages: int


@dataclass(frozen=True)
class NoTextLayer:
    """整份 PDF 都沒有文字層，回傳的是頁面影像。"""


@dataclass(frozen=True)
class PagesRendered:
    """混合型 PDF 中，這些頁沒有文字層，改以影像回傳。"""

    pages: tuple[int, ...]


@dataclass(frozen=True)
class FirstSheetOnly:
    """Google 試算表匯出成 CSV 時，Drive 只會匯出第一個工作表。"""


@dataclass(frozen=True)
class ImageResized:
    original_width: int
    original_height: int


@dataclass(frozen=True)
class FirstFrameOnly:
    """動畫圖片只取第一格。"""


@dataclass(frozen=True)
class UndecodableCharacters:
    """檔案不是 UTF-8，無法解碼的字元已用替代字元表示。"""


Note = (
    TextTruncated
    | PagesOmitted
    | NoTextLayer
    | PagesRendered
    | FirstSheetOnly
    | ImageResized
    | FirstFrameOnly
    | UndecodableCharacters
)


@dataclass(frozen=True)
class Content:
    parts: tuple[TextPart | ImagePart, ...]
    notes: tuple[Note, ...] = ()


# ---------- 完全無法交付內容 ----------


class LimitationReason(StrEnum):
    UNSUPPORTED_TYPE = "unsupported_type"
    TOO_LARGE = "too_large"
    EXPORT_TOO_LARGE = "export_too_large"
    PASSWORD_PROTECTED = "password_protected"
    DAMAGED = "damaged"
    IMAGE_FORMAT_UNSUPPORTED = "image_format_unsupported"


@dataclass(frozen=True)
class ReadLimitation:
    reason: LimitationReason
