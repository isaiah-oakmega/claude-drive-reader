"""設定（C5）：缺少必填變數時啟動就失敗，錯誤訊息只列出變數名稱，不印出任何值。"""

import pytest

from token_broker.settings import MissingSettings, Settings

COMPLETE = {
    "GOOGLE_CLIENT_ID": "client-123.apps.googleusercontent.com",
    "GOOGLE_CLIENT_SECRET": "s3cr3t-value",
    "PUBLIC_BASE_URL": "https://broker.example/",
}


def test_redirect_uri_is_derived_from_public_base_url() -> None:
    settings = Settings.from_env(COMPLETE)

    # 結尾斜線被去掉，redirect_uri 永遠是 ${PUBLIC_BASE_URL}/callback（B5）
    assert settings.redirect_uri == "https://broker.example/callback"


@pytest.mark.parametrize("missing", list(COMPLETE))
def test_missing_variable_fails_fast_and_names_it(missing: str) -> None:
    env = {k: v for k, v in COMPLETE.items() if k != missing}

    with pytest.raises(MissingSettings) as excinfo:
        Settings.from_env(env)

    assert missing in str(excinfo.value)
    assert "s3cr3t-value" not in str(excinfo.value)


def test_secret_is_not_in_repr() -> None:
    assert "s3cr3t-value" not in repr(Settings.from_env(COMPLETE))
