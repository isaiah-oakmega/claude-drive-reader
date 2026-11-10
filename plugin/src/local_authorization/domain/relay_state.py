"""C1 的 state 格式：<port>.<nonce>。本機負責產生，Broker 負責檢查格式（B2），兩邊各自實作。"""

import re
import secrets

from local_authorization.domain.limits import MAX_CALLBACK_PORT, MIN_CALLBACK_PORT

# 和 backend 的 token_broker/domain/code_relay.py 是同一個格式，由兩邊的合約測試
# （state_vectors.json）鎖住。port 不得有前導零；nonce 是 16–128 個 base64url 字元。
_STATE_PATTERN = re.compile(r"([1-9][0-9]{3,4})\.([A-Za-z0-9_-]{16,128})", re.ASCII)


def is_valid_relay_state(state: str) -> bool:
    match = _STATE_PATTERN.fullmatch(state)
    return match is not None and MIN_CALLBACK_PORT <= int(match.group(1)) <= MAX_CALLBACK_PORT


def new_relay_state(port: int) -> str:
    # 32 bytes 的隨機值，base64url 後 43 字元。這是 state 中唯一無法猜到的部分，
    # 本機只接受帶著它回來的 callback（A2）。
    state = f"{port}.{secrets.token_urlsafe(32)}"
    if not is_valid_relay_state(state):
        # 只會發生在 port 超出範圍時；在這裡就擋下，不要等 Broker 回 400 才發現
        raise ValueError(f"callback port {port} is outside {MIN_CALLBACK_PORT}-{MAX_CALLBACK_PORT}")
    return state
