"""Local Credential 檔案（A4）：權限不寬於 0600，寫入不會只寫一半。"""

import json
import os
import secrets
import sys
from pathlib import Path

from local_authorization.domain.credential import LocalCredential


class CredentialStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def permissions_enforced(self) -> bool:
        # Windows 忽略 os.open 的 mode。保護來自檔案位於使用者設定檔目錄下、預設 ACL 只允許本人存取；
        # 程式不另外設 ACL，所以不能宣稱 Windows 上有 0600（A4 的 Windows 例外）。
        return sys.platform != "win32"

    def load(self) -> LocalCredential | None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            credential = LocalCredential(
                refresh_token=data["refresh_token"], scope=data["scope"], obtained_at=data["obtained_at"]
            )
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError, KeyError):
            # 檔案壞了就當作沒有授權：使用者重新 authorize 時會整個覆寫。
            # 不在這裡刪檔，留給使用者檢查，也避免誤刪別的程式寫在同一路徑的檔案。
            return None
        if not all(isinstance(value, str) and value for value in vars(credential).values()):
            return None
        return credential

    def save(self, credential: LocalCredential) -> None:
        directory = self.path.parent
        if not directory.exists():
            # 只有自己建立的目錄才設成 0700。使用者指定的既有目錄（例如 /tmp）不能改它的權限。
            # umask 只會把權限變得更嚴，不會變寬，所以結果一定不寬於 0700。
            directory.mkdir(mode=0o700, parents=True)

        # 先寫到同一個目錄下的暫存檔，再用 os.replace 換上去：replace 是原子操作，
        # 程式在任何時間點中斷，檔案不是舊的完整內容就是新的完整內容。
        temp = directory / f".{self.path.name}.{secrets.token_hex(8)}.tmp"
        # O_EXCL：暫存檔一定是這次新建的，不會寫進別人預先放好的檔案或 symlink。
        # 0o600 在建立的瞬間就生效，檔案不會有任何一刻是其他人可讀的。
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as file:
                json.dump(vars(credential), file)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.path)
        except BaseException:
            temp.unlink(missing_ok=True)
            raise

    def delete(self) -> bool:
        try:
            self.path.unlink()
        except FileNotFoundError:
            return False
        return True
