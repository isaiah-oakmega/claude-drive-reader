"""產生真實驗收用的測試檔（上傳到開發用的 Root Folder 後，用 read_file 讀取）。

執行（在 repo 根目錄）：
    uv run --directory plugin python ../docs/acceptance-files/make_files.py

PDF 用 plugin/tests/support/pdf_builder.py 產生：掃描頁是「畫在影像上的文字」，沒有文字層。
中文字型使用系統的 Noto Sans CJK；找不到時改用英文。
"""

import io
import sys
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "plugin" / "tests" / "support"))
from pdf_builder import build_pdf, text_page  # noqa: E402

CJK_FONT = Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if CJK_FONT.exists():
        # .ttc 裡有多種語系，找繁體中文（TC）那一個
        for index in range(10):
            try:
                candidate = ImageFont.truetype(str(CJK_FONT), size, index=index)
            except OSError:
                break
            if "TC" in " ".join(candidate.getname()):
                return candidate
    return ImageFont.load_default(size)


def scanned_page(lines: list[str]) -> tuple[int, int, bytes]:
    # A4、100 dpi：夠清楚，PDF 也不會太大
    image = Image.new("RGB", (827, 1170), "white")
    draw = ImageDraw.Draw(image)
    body = font(30)
    for row, line in enumerate(lines):
        draw.text((80, 100 + row * 56), line, fill="black", font=body)
    return (*image.size, image.tobytes())


def main() -> None:
    pages = [
        scanned_page([f"掃描文件 第 {n} 頁", "這一頁是影像，沒有文字層。", f"驗收代碼：SCAN-{n:02d}"]) for n in range(1, 7)
    ]
    (HERE / "掃描型.pdf").write_bytes(build_pdf(*pages))

    english = "This page has a real text layer. Acceptance code: TEXT-{0:02d}. The quick brown fox jumps over the lazy dog."
    (HERE / "混合型.pdf").write_bytes(
        build_pdf(
            text_page(english.format(1)),
            scanned_page(["混合型 PDF 第 2 頁", "這一頁是掃描影像。", "驗收代碼：MIXED-02"]),
            text_page(english.format(3)),
        )
    )

    big = Image.new("RGB", (4000, 3000), (235, 245, 255))
    draw = ImageDraw.Draw(big)
    draw.rectangle((400, 400, 3600, 2600), outline=(20, 60, 160), width=40)
    draw.text((700, 1200), "大圖片 4000×3000：長邊應縮成 1568px", fill=(20, 60, 160), font=font(150))
    big.save(HERE / "大圖片.png")

    frames = [Image.new("RGB", (300, 200), color) for color in ((220, 40, 40), (40, 160, 60), (40, 80, 220))]
    for frame, label in zip(frames, ("第一格：紅色", "第二格：綠色", "第三格：藍色"), strict=True):
        ImageDraw.Draw(frame).text((30, 80), label, fill="white", font=font(32))
    frames[0].save(HERE / "動畫.gif", save_all=True, append_images=frames[1:], duration=600, loop=0)

    (HERE / "big5編碼.txt").write_bytes("這是 Big5 編碼的舊文字檔，不是 UTF-8。\r\n驗收代碼：BIG5-01\r\n".encode("big5"))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("readme.txt", "Drive Reader 不解析壓縮檔。")
    (HERE / "不支援.zip").write_bytes(buffer.getvalue())

    for path in sorted(HERE.iterdir()):
        if path.suffix != ".py" and path.name != "README.md":
            print(f"{path.name}: {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
