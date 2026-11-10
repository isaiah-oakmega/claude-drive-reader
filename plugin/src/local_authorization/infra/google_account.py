"""目前授權帳號的 email（C2 的 current_account）。

用 Drive 的 about.get 取得，不另外要求 email scope（實作規格「安全邊界」）。
它讀的是帳號資訊而不是檔案內容，所以放在 Local Authorization，不放在 Drive Reading。
"""

import httpx2

ABOUT_ENDPOINT = "https://www.googleapis.com/drive/v3/about"


class GoogleAccount:
    def __init__(self, http: httpx2.Client) -> None:
        self._http = http

    def email(self, access_token: str) -> str | None:
        # 拿不到就回 None：email 只用來讓訊息更好懂（R6、auth_status），不能因為它讓原本的操作失敗
        try:
            response = self._http.get(
                ABOUT_ENDPOINT,
                params={"fields": "user(emailAddress)"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code != 200:
                return None
            email = response.json().get("user", {}).get("emailAddress")
        except (httpx2.HTTPError, ValueError, AttributeError):
            return None
        return email if isinstance(email, str) and email else None
