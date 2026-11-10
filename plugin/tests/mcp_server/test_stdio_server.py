"""組裝根：用和 .mcp.json 相同的方式（python -m mcp_server）啟動，透過 stdio 完成 MCP 握手。"""

import os
import subprocess
import sys
from pathlib import Path

import anyio
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def list_tool_names(env: dict[str, str]) -> list[str]:
    params = StdioServerParameters(command=sys.executable, args=["-m", "mcp_server"], env=env)
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return [tool.name for tool in (await session.list_tools()).tools]


def test_server_starts_over_stdio_and_lists_authorization_tools(tmp_path: Path) -> None:
    # 啟動不需要網路，也不會建立 credential 檔
    env = dict(os.environ, DRIVE_READER_CREDENTIALS_PATH=str(tmp_path / "credentials.json"))

    names = anyio.run(list_tool_names, env)

    # 只有正式的 tool；階段 2 的 spike_image 已經移除
    assert sorted(names) == ["auth_status", "authorize", "logout"]
    assert not (tmp_path / "credentials.json").exists()


def test_invalid_config_stops_startup_with_variable_name(tmp_path: Path) -> None:
    env = dict(os.environ, DRIVE_READER_CALLBACK_PORT="80")

    finished = subprocess.run(
        [sys.executable, "-m", "mcp_server"], env=env, capture_output=True, encoding="utf-8", timeout=30, stdin=subprocess.DEVNULL
    )

    assert finished.returncode != 0
    assert "DRIVE_READER_CALLBACK_PORT" in finished.stderr
    assert "設定錯誤" in finished.stderr
    # stdout 是 MCP 的通訊管道，錯誤訊息只能寫到 stderr
    assert finished.stdout == ""
