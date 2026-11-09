"""階段 0 的煙霧測試：確認套件與四個分層都能被 import，打包設定沒有漏掉。"""

import importlib

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "token_broker",
        "token_broker.domain",
        "token_broker.app",
        "token_broker.infra",
        "token_broker.api",
    ],
)
def test_layer_is_importable(module: str) -> None:
    importlib.import_module(module)
