"""Broker 回給瀏覽器的 HTML。

B6：所有頁面都是事先寫好的固定內容。錯誤頁依錯誤種類挑選訊息，絕不把請求參數放進 HTML，
因此不需要做任何跳脫（escape），也就不會有跳脫遺漏造成的反射型 XSS。
"""

from enum import Enum


class ErrorKind(Enum):
    INVALID_AUTHORIZE_REQUEST = "invalid_authorize_request"
    INVALID_CALLBACK = "invalid_callback"


_ERROR_MESSAGES = {
    ErrorKind.INVALID_AUTHORIZE_REQUEST: (
        "授權請求格式不正確",
        "請回到 Claude Code，重新要求授權（例如說「請重新授權 Google Drive」）。",
    ),
    ErrorKind.INVALID_CALLBACK: (
        "無法完成授權轉交",
        "這個連結可能已失效或被修改過。請回到 Claude Code，重新要求授權。",
    ),
}


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · Drive Reader</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.7; color: #1d2224; }}
  h1 {{ font-size: 1.4rem; }}
  code {{ background: #eef1ef; padding: 0 .3em; border-radius: 3px; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def home_page() -> str:
    return _page(
        "Drive Reader",
        """<h1>Drive Reader</h1>
<p>Drive Reader 是一個 Claude Code plugin，讓你在 Claude Code 中用自然語言讀取指定的 Google Drive 資料夾。</p>
<p>這個網站是它的授權服務（Token Broker）：只負責在授權過程中代為向 Google 交換 token，
不保存任何 token，也不讀取任何檔案內容。</p>
<p><a href="/privacy">隱私權政策</a></p>""",
    )


def privacy_page() -> str:
    return _page(
        "隱私權政策",
        """<h1>隱私權政策</h1>
<p>Drive Reader 只要求 <code>https://www.googleapis.com/auth/drive.readonly</code> 這一個權限（唯讀）。</p>
<h2>我們會經手的資料</h2>
<ul>
  <li>授權時，Google 回傳的授權碼會經過本服務轉交到你的電腦。</li>
  <li>交換或更新 token 時，token 會經過本服務傳回你的電腦。</li>
</ul>
<h2>我們不會做的事</h2>
<ul>
  <li>不保存任何授權碼、access token 或 refresh token，也不寫進記錄。</li>
  <li>不讀取、不保存、不轉送你的任何 Google Drive 檔案；檔案只在你的電腦上被讀取。</li>
  <li>不與任何第三方分享資料。</li>
</ul>
<h2>撤銷授權</h2>
<p>你可以隨時在 Claude Code 中登出（會向 Google 撤銷授權並刪除本機的 token），
或到 Google 帳戶的「第三方存取權」頁面移除 Drive Reader。</p>""",
    )


def error_page(kind: ErrorKind) -> str:
    title, advice = _ERROR_MESSAGES[kind]
    return _page(title, f"<h1>{title}</h1>\n<p>{advice}</p>")
