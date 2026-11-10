"""圖片：用 Pillow 縮到長邊 1568px、轉成 Claude 能讀的 PNG 或 JPEG（R4、情境 7）。"""

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from drive_reading.domain.limits import MAX_IMAGE_SIDE
from drive_reading.domain.outcomes import (
    FirstFrameOnly,
    ImagePart,
    ImageResized,
    LimitationReason,
    Note,
    ReadLimitation,
)

# Claude 對單張圖片的上限是 5MB（base64 之前約 3.75MB）。透明的 PNG 超過這個大小就改用 JPEG。
_MAX_ENCODED_BYTES = 3_750_000


def prepare_image(data: bytes) -> tuple[ImagePart, tuple[Note, ...]] | ReadLimitation:
    try:
        image = Image.open(io.BytesIO(data))
        notes: list[Note] = []
        if getattr(image, "n_frames", 1) > 1:
            # 動畫 GIF、WebP：只取第一格
            notes.append(FirstFrameOnly())
        image.seek(0)
        image.load()
    except Image.DecompressionBombError:
        # 檔案不大，解壓後卻有上億個像素：處理它會吃光記憶體
        return ReadLimitation(LimitationReason.TOO_LARGE)
    except UnidentifiedImageError:
        # Pillow 不認得的格式，例如 HEIC
        return ReadLimitation(LimitationReason.IMAGE_FORMAT_UNSUPPORTED)
    except (OSError, SyntaxError, ValueError):
        # 檔案不完整或內容損壞
        return ReadLimitation(LimitationReason.DAMAGED)

    # 手機照片常用 EXIF 記錄方向，不轉正的話 Claude 會看到躺著的照片
    image = ImageOps.exif_transpose(image)
    original = image.size
    part = encode_image(image)
    if (part.width, part.height) != original:
        notes.append(ImageResized(original_width=original[0], original_height=original[1]))
    return part, tuple(notes)


def encode_image(image: Image.Image, page: int | None = None) -> ImagePart:
    """縮小並編碼。PDF 算繪出來的頁面也走這裡，兩者的大小與格式規則一致。"""
    image = image.copy()
    # thumbnail 只縮不放，維持長寬比
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
    if _has_alpha(image):
        data = _encode(image.convert("RGBA"), "PNG")
        if len(data) <= _MAX_ENCODED_BYTES:
            return ImagePart(data=data, mime_type="image/png", width=image.width, height=image.height, page=page)
        # 太大的透明圖：鋪上白底改用 JPEG
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.convert("RGBA").getchannel("A"))
        image = background
    # 不透明的圖用 JPEG：照片與掃描頁的檔案小很多，品質 85 對閱讀內容沒有影響
    data = _encode(image.convert("RGB"), "JPEG", quality=85)
    return ImagePart(data=data, mime_type="image/jpeg", width=image.width, height=image.height, page=page)


def _has_alpha(image: Image.Image) -> bool:
    return image.mode in ("RGBA", "LA", "PA") or (image.mode == "P" and "transparency" in image.info)


def _encode(image: Image.Image, image_format: str, **options: int) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, image_format, **options)
    return buffer.getvalue()
