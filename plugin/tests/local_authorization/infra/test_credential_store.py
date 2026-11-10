"""A4：Local Credential 檔案的權限與原子寫入；A5、A6 需要的刪除。"""

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from local_authorization.domain.credential import LocalCredential
from local_authorization.infra.credential_store import CredentialStore

CREDENTIAL = LocalCredential(refresh_token="1//REFRESH", scope="https://www.googleapis.com/auth/drive.readonly", obtained_at="2026-11-10T10:00:00+00:00")
posix_only = pytest.mark.skipif(sys.platform == "win32", reason="Windows 忽略 POSIX 權限位元（A4 的 Windows 例外）")


@pytest.fixture
def store(tmp_path: Path) -> CredentialStore:
    return CredentialStore(tmp_path / "claude-drive-reader" / "credentials.json")


def test_missing_file_means_no_credential(store: CredentialStore) -> None:
    assert store.load() is None


def test_save_then_load_round_trips(store: CredentialStore) -> None:
    store.save(CREDENTIAL)

    assert store.load() == CREDENTIAL


def test_file_contains_only_the_credential_fields(store: CredentialStore) -> None:
    store.save(CREDENTIAL)

    assert json.loads(store.path.read_text(encoding="utf-8")) == {
        "refresh_token": "1//REFRESH",
        "scope": "https://www.googleapis.com/auth/drive.readonly",
        "obtained_at": "2026-11-10T10:00:00+00:00",
    }


@posix_only
def test_file_is_0600_and_new_directory_is_0700(store: CredentialStore) -> None:
    store.save(CREDENTIAL)

    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(store.path.parent.stat().st_mode) == 0o700


@posix_only
def test_overwrite_keeps_0600_even_with_permissive_umask(store: CredentialStore) -> None:
    old_umask = os.umask(0)
    try:
        store.save(CREDENTIAL)
        store.save(LocalCredential(refresh_token="1//NEW", scope=CREDENTIAL.scope, obtained_at=CREDENTIAL.obtained_at))
    finally:
        os.umask(old_umask)

    assert stat.S_IMODE(store.path.stat().st_mode) == 0o600
    assert store.load().refresh_token == "1//NEW"


@posix_only
def test_existing_directory_permissions_are_left_alone(tmp_path: Path) -> None:
    # 使用者把 DRIVE_READER_CREDENTIALS_PATH 指到既有目錄時，不能去改那個目錄的權限
    shared = tmp_path / "shared"
    shared.mkdir(mode=0o755)
    os.chmod(shared, 0o755)

    CredentialStore(shared / "credentials.json").save(CREDENTIAL)

    assert stat.S_IMODE(shared.stat().st_mode) == 0o755


def test_reports_whether_posix_permissions_protect_the_file(store: CredentialStore) -> None:
    # Windows 上不宣稱 0600（A4）：呼叫端依這個值決定怎麼描述檔案的保護方式
    assert store.permissions_enforced is (sys.platform != "win32")


def test_failed_write_leaves_previous_file_and_no_temp_files(store: CredentialStore, monkeypatch: pytest.MonkeyPatch) -> None:
    store.save(CREDENTIAL)

    def broken_replace(src: str, dst: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken_replace)
    with pytest.raises(OSError):
        store.save(LocalCredential(refresh_token="1//NEW", scope=CREDENTIAL.scope, obtained_at=CREDENTIAL.obtained_at))

    assert store.load() == CREDENTIAL
    assert sorted(p.name for p in store.path.parent.iterdir()) == ["credentials.json"]


@pytest.mark.parametrize(
    "content",
    ["", "not json", "[]", '{"scope": "x"}', '{"refresh_token": 42, "scope": "x", "obtained_at": "t"}'],
    ids=["empty", "not-json", "list", "missing-token", "wrong-type"],
)
def test_unreadable_file_is_treated_as_no_credential(store: CredentialStore, content: str) -> None:
    store.path.parent.mkdir(parents=True)
    store.path.write_text(content, encoding="utf-8")

    assert store.load() is None


def test_delete_removes_file_and_reports_it(store: CredentialStore) -> None:
    store.save(CREDENTIAL)

    assert store.delete() is True
    assert store.path.exists() is False
    assert store.delete() is False
