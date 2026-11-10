"""C3 合約測試：實際註冊的 tool、必填參數、Failure 代碼，和 docs/implementation-spec.md 的 C3 表格一致。

直接讀規格文件的表格，而不是在測試裡再抄一份：規格改了而程式沒改（或反過來）時，這裡會失敗。
"""

import re
from pathlib import Path

import anyio
import pytest

from drive_reading.app import GoogleApiError, NotAFile, NotFoundOrNoAccess, OutsideRoot
from local_authorization.app import AuthExpired, BrokerUnreachable, CallbackPortUnavailable, NotAuthorized
from mcp_server.__main__ import build_server
from mcp_server.config import Config
from mcp_server.failures import failure_text

SPEC = Path(__file__).parents[3] / "docs" / "implementation-spec.md"
pytestmark = pytest.mark.skipif(not SPEC.exists(), reason="只有在完整 repo 中執行時才有規格文件")

# 每一種 Failure 各一個例子；新增例外種類時要加在這裡
SAMPLE_FAILURES = [
    NotAuthorized(),
    AuthExpired(),
    BrokerUnreachable("https://broker.example"),
    CallbackPortUnavailable(50000),
    NotFoundOrNoAccess("x"),
    OutsideRoot("x"),
    NotAFile("x"),
    GoogleApiError(500, "backendError"),
]


def c3_section() -> str:
    text = SPEC.read_text(encoding="utf-8")
    return text[text.index("### C3 MCP Tools") : text.index("### C4")]


def spec_tools() -> dict[str, str]:
    """C3 第一張表：tool 名稱 → 參數欄。"""
    rows = re.findall(r"^\| `(\w+)` \| (.*?) \|", c3_section(), re.MULTILINE)
    return {name: params for name, params in rows if name.islower()}


def spec_failure_codes() -> set[str]:
    return set(re.findall(r"^\| `([A-Z_]+)` \|", c3_section(), re.MULTILINE))


@pytest.fixture(scope="module")
def tools(tmp_path_factory) -> dict:
    home = tmp_path_factory.mktemp("home")
    server = build_server(Config.from_env({}, home=home))
    return {tool.name: tool for tool in anyio.run(server.list_tools)}


def test_registered_tools_match_spec(tools: dict) -> None:
    assert set(tools) == set(spec_tools())


def test_required_parameters_match_spec(tools: dict) -> None:
    for name, params in spec_tools().items():
        # 規格的參數欄：`file` 是必填；`folder?` 與 `recursive=True` 是選填；「—」代表沒有參數
        required = sorted(re.findall(r"`(\w+)`(?![?=])", params))
        assert sorted(tools[name].input_schema.get("required", [])) == required, name


def test_every_spec_failure_code_is_produced_and_nothing_else() -> None:
    produced = {re.match(r"\[([A-Z_]+)\]", failure_text(error)).group(1) for error in SAMPLE_FAILURES}

    assert produced == spec_failure_codes()


def test_descriptions_are_bilingual(tools: dict) -> None:
    for name, tool in tools.items():
        assert re.search(r"[A-Za-z]{4,}", tool.description), name
        assert re.search(r"[一-鿿]", tool.description), name
