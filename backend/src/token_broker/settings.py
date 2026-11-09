"""Broker 的設定（C5）：全部來自環境變數，正式環境由 Cloud Run 注入，secret 來自 Secret Manager。"""

from collections.abc import Mapping
from dataclasses import dataclass, field

_REQUIRED = ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "PUBLIC_BASE_URL")


class MissingSettings(RuntimeError):
    """缺少必要的環境變數。訊息只列名稱，不含任何值。"""


@dataclass(frozen=True)
class Settings:
    client_id: str
    # repr=False：Settings 被印出或寫進錯誤訊息時，不會連 secret 一起洩漏
    client_secret: str = field(repr=False)
    public_base_url: str

    @property
    def redirect_uri(self) -> str:
        # B5：redirect_uri 只有這一個來源，/authorize 與 /token 一定一致
        return f"{self.public_base_url}/callback"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        # 啟動時就檢查：缺設定的服務直接起不來，比上線後第一個使用者授權時才失敗容易發現
        missing = [name for name in _REQUIRED if not env.get(name)]
        if missing:
            raise MissingSettings(f"缺少必要的環境變數：{', '.join(missing)}")
        return cls(
            client_id=env["GOOGLE_CLIENT_ID"],
            client_secret=env["GOOGLE_CLIENT_SECRET"],
            # 去掉結尾斜線，避免組出 https://host//callback 這種和 Google 設定不一致的 redirect_uri
            public_base_url=env["PUBLIC_BASE_URL"].rstrip("/"),
        )
