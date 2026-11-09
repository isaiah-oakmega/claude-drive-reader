"""B2：Code Relay 只能轉到 http://127.0.0.1:<port>/callback，state 格式由合約測試向量鎖住。"""

import json
from pathlib import Path

import pytest

from token_broker.domain.code_relay import RelayState
from token_broker.domain.errors import InvalidState

VECTORS = json.loads(
    (Path(__file__).parent.parent / "contract" / "state_vectors.json").read_text(encoding="utf-8")
)


@pytest.mark.parametrize("case", VECTORS["valid"], ids=lambda c: c["state"][:12])
def test_valid_state_yields_port(case: dict) -> None:
    assert RelayState.parse(case["state"]).port == case["port"]


@pytest.mark.parametrize("case", VECTORS["invalid"], ids=lambda c: c["why"])
def test_invalid_state_is_rejected(case: dict) -> None:
    with pytest.raises(InvalidState):
        RelayState.parse(case["state"])


def test_relay_target_is_always_loopback() -> None:
    state = RelayState.parse(VECTORS["valid"][2]["state"])

    assert state.loopback_callback_url() == "http://127.0.0.1:53682/callback"
