"""打包檢查（CI 的 package job）：照 .mcp.json 的指令啟動 MCP server，完成握手並確認五個 tool 都在。

和 Claude Code 安裝 plugin 後的啟動方式完全相同（`uv run --frozen --no-dev --directory <plugin>`），
所以能抓到「測試會過、但裝起來跑不動」的問題：pyproject 漏列套件、lockfile 缺依賴、模組名稱衝突（風險 #10）。

用法（在 plugin/ 目錄）：uv run --frozen --no-dev python scripts/mcp_handshake.py
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_TOOLS = {"authorize", "auth_status", "logout", "list_files", "read_file"}
# 第一次啟動要下載 Python 與套件；超過這個時間就當成失敗（風險 #4）
STARTUP_TIMEOUT_SECONDS = 120


async def handshake() -> set[str]:
    server = json.loads((PLUGIN_ROOT / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["drive"]
    args = [arg.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN_ROOT)) for arg in server["args"]]
    params = StdioServerParameters(command=server["command"], args=args, env=dict(os.environ))
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return {tool.name for tool in (await session.list_tools()).tools}


def main() -> None:
    started = time.monotonic()
    tools = asyncio.run(asyncio.wait_for(handshake(), STARTUP_TIMEOUT_SECONDS))
    elapsed = time.monotonic() - started
    print(f"handshake ok in {elapsed:.1f}s, tools: {sorted(tools)}")
    if tools != EXPECTED_TOOLS:
        print(f"expected {sorted(EXPECTED_TOOLS)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
