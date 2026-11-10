"""SPIKE（暫時）：回傳一張測試圖片，實測 Claude Code 會不會把 MCP 的 image content 交給模型（風險 #1）。

圖片是三條直條紋，顏色刻意不寫在 tool 描述裡：模型只有真的看到圖片，才說得出顏色。
用標準函式庫手動組 PNG，避免為了 spike 先引入 Pillow。階段 2 結束前刪除。
"""

import struct
import zlib

from mcp.server.mcpserver import Image, MCPServer

_STRIPES = [(255, 221, 0), (0, 0, 0), (230, 0, 230)]


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    body = kind + payload
    return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))


def stripes_png(width: int = 96, height: int = 48) -> bytes:
    stripe_width = width // len(_STRIPES)
    row = b"".join(bytes(_STRIPES[min(x // stripe_width, len(_STRIPES) - 1)]) for x in range(width))
    raw = b"".join(b"\x00" + row for _ in range(height))
    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def register(server: MCPServer) -> None:
    @server.tool(description="Spike test only: returns a small test image. 測試用：回傳一張測試圖片。")
    def spike_image() -> Image:
        return Image(data=stripes_png(), format="png")
