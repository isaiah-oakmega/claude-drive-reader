"""C1 的 state 格式合約（實作規格「Repo 形態」規則 5）。

state_vectors.json 是從 backend/tests/contract/ 複製過來的同一份內容：Broker 用它驗證「接受什麼」，
這裡用它驗證本機「產生的 state 一定會被 Broker 接受」。兩份檔案必須保持一致。
"""

import json
from pathlib import Path

import pytest

from local_authorization.domain.relay_state import is_valid_relay_state, new_relay_state

VECTORS = json.loads((Path(__file__).parent / "state_vectors.json").read_text(encoding="utf-8"))


def test_vectors_match_the_backend_copy() -> None:
    backend_copy = Path(__file__).parents[3] / "backend" / "tests" / "contract" / "state_vectors.json"
    if not backend_copy.exists():
        pytest.skip("只有在完整 repo 中執行時才比對兩份檔案")
    assert backend_copy.read_text(encoding="utf-8") == (Path(__file__).parent / "state_vectors.json").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("vector", VECTORS["valid"], ids=lambda v: v["state"][:20])
def test_valid_vectors_are_accepted(vector: dict) -> None:
    assert is_valid_relay_state(vector["state"])


@pytest.mark.parametrize("vector", VECTORS["invalid"], ids=lambda v: v["why"])
def test_invalid_vectors_are_rejected(vector: dict) -> None:
    assert not is_valid_relay_state(vector["state"])


@pytest.mark.parametrize("port", [1024, 53682, 65535])
def test_generated_state_is_accepted_by_the_broker_format(port: int) -> None:
    state = new_relay_state(port)

    assert is_valid_relay_state(state)
    assert state.startswith(f"{port}.")


def test_generated_nonces_differ() -> None:
    assert new_relay_state(53682) != new_relay_state(53682)


@pytest.mark.parametrize("port", [0, 80, 1023, 65536])
def test_port_outside_relay_range_is_refused(port: int) -> None:
    with pytest.raises(ValueError):
        new_relay_state(port)
