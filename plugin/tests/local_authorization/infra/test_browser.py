"""開瀏覽器：失敗只回傳 False（情境 2 由使用者手動點網址），而且子程序的輸出不能進到 MCP 的 stdout。"""

import subprocess
import sys

import pytest

from local_authorization.infra import browser

URL = "https://broker.example/authorize?state=x"
not_windows = pytest.mark.skipif(sys.platform == "win32", reason="Windows 用 os.startfile，不啟動子程序")


@not_windows
def test_opener_output_is_discarded(monkeypatch: pytest.MonkeyPatch) -> None:
    launched: list[tuple[list[str], dict]] = []
    monkeypatch.setattr(browser.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(browser.subprocess, "Popen", lambda args, **kwargs: launched.append((args, kwargs)))

    assert browser.open_url(URL) is True

    args, kwargs = launched[0]
    assert args[-1] == URL
    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL


@not_windows
def test_missing_opener_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser.shutil, "which", lambda name: None)

    assert browser.open_url(URL) is False


@not_windows
def test_opener_failure_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args, **kwargs):
        raise OSError("exec failed")

    monkeypatch.setattr(browser.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(browser.subprocess, "Popen", fail)

    assert browser.open_url(URL) is False
