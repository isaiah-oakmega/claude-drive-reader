"""階段 0 的煙霧測試：確認三個最上層套件與各 context 的分層都能被 import，打包清單沒有漏掉。"""

import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "local_authorization",
        "local_authorization.domain",
        "local_authorization.app",
        "local_authorization.infra",
        "drive_reading",
        "drive_reading.domain",
        "drive_reading.app",
        "drive_reading.infra",
        "mcp_server",
    ],
)
def test_package_is_importable(module: str) -> None:
    importlib.import_module(module)
