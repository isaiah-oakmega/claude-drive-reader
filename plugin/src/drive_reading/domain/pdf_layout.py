"""R4a：PDF 逐頁決定回傳文字或影像，依頁碼順序穿插，並套用 R4 的上限。

這裡只有規則。抽文字與算繪由 infra 的 PDF 函式庫提供，以函式傳入：
只有真的要用影像的頁面才會被算繪，算繪很耗時間與記憶體。
"""

from collections.abc import Callable

from drive_reading.domain.limits import (
    MAX_RENDERED_PAGES,
    MAX_TEXT_CHARS,
    MAX_TEXT_CHARS_WITH_IMAGES,
    MIN_TEXT_CHARS_PER_PAGE,
)
from drive_reading.domain.outcomes import (
    Content,
    ImagePart,
    Note,
    NoTextLayer,
    PagesOmitted,
    PagesRendered,
    TextPart,
    TextTruncated,
)


def assemble_pdf(page_count: int, page_text: Callable[[int], str], render_page: Callable[[int], ImagePart]) -> Content:
    parts: list[TextPart | ImagePart] = []
    rendered: list[int] = []
    used_chars = 0
    truncated_at: int | None = None
    omitted_from: int | None = None

    for index in range(page_count):
        number = index + 1
        text = page_text(index)
        # 已經放了影像，文字預算就降到 10,000 字（見 limits.py 的說明）
        text_budget = MAX_TEXT_CHARS_WITH_IMAGES if rendered else MAX_TEXT_CHARS

        if sum(not ch.isspace() for ch in text) >= MIN_TEXT_CHARS_PER_PAGE:
            room = text_budget - used_chars
            if room <= 0:
                omitted_from = number
                break
            if len(text) > room:
                parts.append(TextPart(text=text[:room], page=number))
                used_chars += room
                truncated_at = text_budget
                if number < page_count:
                    omitted_from = number + 1
                break
            parts.append(TextPart(text=text, page=number))
            used_chars += len(text)
        else:
            # 沒有文字層的頁面：影像額度用完，或文字已經多到放不下影像，就從這一頁開始省略
            if len(rendered) == MAX_RENDERED_PAGES or used_chars > MAX_TEXT_CHARS_WITH_IMAGES:
                omitted_from = number
                break
            parts.append(render_page(index))
            rendered.append(number)

    notes: list[Note] = []
    if rendered:
        has_text = any(isinstance(part, TextPart) for part in parts)
        notes.append(PagesRendered(pages=tuple(rendered)) if has_text else NoTextLayer())
    if truncated_at is not None:
        notes.append(TextTruncated(limit_chars=truncated_at))
    if omitted_from is not None:
        notes.append(PagesOmitted(from_page=omitted_from, total_pages=page_count))
    return Content(parts=tuple(parts), notes=tuple(notes))
