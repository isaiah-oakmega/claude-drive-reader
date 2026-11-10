"""C5 設定合約：本機的四個環境變數與預設值。"""

from pathlib import Path

import pytest

from mcp_server.config import Config, InvalidConfig

HOME = Path("/home/someone")


def test_defaults() -> None:
    config = Config.from_env({}, home=HOME)

    assert config.broker_url == "https://drive-auth.isaiahlin.dev"
    assert config.root_folder == "1AU6ZW-3NFxme6388YPe98bGWWh9q_E5Y"
    assert config.credentials_path == HOME / ".config" / "claude-drive-reader" / "credentials.json"
    assert config.callback_port is None


def test_every_variable_can_be_overridden(tmp_path: Path) -> None:
    config = Config.from_env(
        {
            "DRIVE_READER_BROKER_URL": "https://broker.example/",
            "DRIVE_READER_ROOT_FOLDER": "https://drive.google.com/drive/folders/abc123",
            "DRIVE_READER_CREDENTIALS_PATH": str(tmp_path / "creds.json"),
            "DRIVE_READER_CALLBACK_PORT": "53682",
        },
        home=HOME,
    )

    assert config.broker_url == "https://broker.example/"
    # Root Folder 的 URL 解析屬於 Drive Reading（階段 3），這裡原樣保留
    assert config.root_folder == "https://drive.google.com/drive/folders/abc123"
    assert config.credentials_path == tmp_path / "creds.json"
    assert config.callback_port == 53682


def test_empty_values_count_as_unset() -> None:
    # .mcp.json 的 env 或 shell 可能傳入空字串；空字串不該變成「Broker 網址是空的」
    names = ["DRIVE_READER_BROKER_URL", "DRIVE_READER_ROOT_FOLDER", "DRIVE_READER_CREDENTIALS_PATH", "DRIVE_READER_CALLBACK_PORT"]

    assert Config.from_env({name: "  " for name in names}, home=HOME) == Config.from_env({}, home=HOME)


def test_tilde_in_credentials_path_means_home() -> None:
    config = Config.from_env({"DRIVE_READER_CREDENTIALS_PATH": "~/drive/creds.json"}, home=HOME)

    assert config.credentials_path == HOME / "drive" / "creds.json"


@pytest.mark.parametrize("value", ["drive-auth.example", "ftp://drive-auth.example", "https://"], ids=["no-scheme", "ftp", "no-host"])
def test_broker_url_must_be_http_url(value: str) -> None:
    with pytest.raises(InvalidConfig, match="DRIVE_READER_BROKER_URL"):
        Config.from_env({"DRIVE_READER_BROKER_URL": value}, home=HOME)


@pytest.mark.parametrize("value", ["abc", "0", "80", "1023", "65536", "-1", "５３６８２", "53682.5"])
def test_callback_port_must_fit_code_relay_range(value: str) -> None:
    # 必須符合 B2：Broker 只轉到 1024–65535。全形數字 int() 會接受，所以要另外擋
    with pytest.raises(InvalidConfig, match="DRIVE_READER_CALLBACK_PORT"):
        Config.from_env({"DRIVE_READER_CALLBACK_PORT": value}, home=HOME)


def test_error_message_does_not_echo_the_value() -> None:
    with pytest.raises(InvalidConfig) as raised:
        Config.from_env({"DRIVE_READER_CALLBACK_PORT": "not-a-port-xyz"}, home=HOME)

    assert "not-a-port-xyz" not in str(raised.value)
