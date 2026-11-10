"""C3 的 list_files：透過 MCPServer 呼叫，背後是真的 DriveReadingService 加上記憶體裡的假 Drive。"""

import anyio
import pytest
from drive_fakes import ROOT_ID, FakeDrive, file, folder, sample_drive
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from drive_reading.app import DriveReadingService
from drive_reading.domain.limits import MAX_LIST_DEPTH, MAX_LIST_ITEMS
from local_authorization.app import NotAuthorized
from mcp_server import tools


def server_for(drive, account: str | None = "someone@example.com") -> MCPServer:
    server = MCPServer("test")
    tools.register_drive_tools(server, DriveReadingService(drive, ROOT_ID), account=lambda: account)
    return server


def call(server: MCPServer, **arguments) -> str:
    result = anyio.run(server.call_tool, "list_files", arguments)
    assert result.is_error is False
    return "\n".join(block.text for block in result.content)


def test_schema_has_optional_folder_and_recursive() -> None:
    tool = next(tool for tool in anyio.run(server_for(sample_drive()).list_tools) if tool.name == "list_files")

    assert set(tool.input_schema["properties"]) == {"folder", "recursive"}
    assert not tool.input_schema.get("required")
    assert any("一" <= ch <= "鿿" for ch in tool.description)


def test_each_line_has_path_type_size_time_and_id() -> None:
    text = call(server_for(sample_drive()))

    assert "Drive Reader 測試" in text
    assert "報告/q1.pdf | application/pdf | 1.0 KB | 2026-11-01 10:00 UTC | q1-id-000001" in text
    assert "readme.txt | text/plain | 120 B |" in text
    # Google 文件沒有 size
    assert "會議記錄 | application/vnd.google-apps.document | — |" in text


def test_shortcut_shows_its_target() -> None:
    # R2：不跟進，只標示目標 ID 與類型
    assert "目標 outside-file-01（application/pdf）" in call(server_for(sample_drive()))


def test_subfolder_listing_names_its_location() -> None:
    text = call(server_for(sample_drive()), folder="reports-id-0001")

    assert "報告/" in text.splitlines()[1]
    assert "q1.pdf |" in text


def test_non_recursive_says_so() -> None:
    text = call(server_for(sample_drive()), recursive=False)

    assert "報告/q1.pdf" not in text
    assert "直接" in text


def test_empty_folder_says_so() -> None:
    assert "空的" in call(server_for(FakeDrive(folder(ROOT_ID, "my-drive", "空資料夾"))))


def test_truncation_is_noted() -> None:
    drive = FakeDrive(folder(ROOT_ID, "my-drive", "大資料夾"), *[file(f"f{i:04}-id-xx", ROOT_ID) for i in range(MAX_LIST_ITEMS + 1)])

    assert f"{MAX_LIST_ITEMS} 筆上限" in call(server_for(drive))


def test_unexpanded_deep_folders_are_noted() -> None:
    chain = [folder("d1-id-000001", ROOT_ID, "d1")] + [
        folder(f"d{i}-id-000001", f"d{i - 1}-id-000001", f"d{i}") for i in range(2, MAX_LIST_DEPTH + 2)
    ]
    text = call(server_for(FakeDrive(folder(ROOT_ID, "my-drive", "深"), *chain)))

    assert "d1/d2/d3/d4/d5/" in text.split("沒有再往下列出")[1]


def test_names_with_pipes_do_not_break_columns() -> None:
    drive = FakeDrive(folder(ROOT_ID, "my-drive", "Root"), file("pipe-id-0001", ROOT_ID, "a | b.pdf"))

    line = next(line for line in call(server_for(drive)).splitlines() if "pipe-id-0001" in line)

    assert line.count(" | ") == 4


# ---------- Failure ----------


def test_inaccessible_root_reports_not_found_with_account() -> None:
    drive = sample_drive()
    drive.hidden.add(ROOT_ID)

    with pytest.raises(ToolError, match=r"\[NOT_FOUND_OR_NO_ACCESS\].*someone@example\.com"):
        anyio.run(server_for(drive).call_tool, "list_files", {})


def test_outside_root_is_reported() -> None:
    with pytest.raises(ToolError, match=r"\[OUTSIDE_ROOT\]"):
        anyio.run(server_for(sample_drive()).call_tool, "list_files", {"folder": "outside-dir-01"})


def test_authorization_failures_pass_through_to_the_same_format() -> None:
    class Unauthorized(FakeDrive):
        def get_item(self, item_id: str):
            raise NotAuthorized

    with pytest.raises(ToolError, match=r"\[NOT_AUTHORIZED\].*authorize"):
        anyio.run(server_for(Unauthorized()).call_tool, "list_files", {})
