"""Use case：Code Relay。把 Google 回傳的結果原樣轉交到使用者本機，不換 token（ADR 0001）。"""

from collections.abc import Mapping
from urllib.parse import urlencode

from token_broker.domain.code_relay import RelayState

# 只轉交本機需要的三個參數：成功時的 code、拒絕時的 error，以及讓本機比對的 state。
# Google 附帶的其他參數（scope、authuser、prompt 等）本機用不到，不轉交就少一些洩漏面。
RELAYED_PARAMS = ("code", "error", "state")


def build_relay_redirect(params: Mapping[str, str]) -> str:
    # state 不合法就丟出 InvalidState，api 層回 400 且不轉址（B2）
    state = RelayState.parse(params.get("state", ""))
    forwarded = {name: params[name] for name in RELAYED_PARAMS if name in params}
    return f"{state.loopback_callback_url()}?{urlencode(forwarded)}"
