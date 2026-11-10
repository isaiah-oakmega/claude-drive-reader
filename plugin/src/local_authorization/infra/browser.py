"""嘗試開啟使用者的瀏覽器。打不開只回傳 False，由使用者手動點 Claude 顯示的網址（情境 2）。

不用標準庫的 webbrowser：它啟動的子程序會繼承 stdout，而 stdout 是 MCP 的通訊管道，
瀏覽器或 xdg-open 印出的任何一行都會讓 Claude Code 收到壞掉的訊息。這裡自己啟動，並把輸出丟掉。
"""

import os
import shutil
import subprocess
import sys


def open_url(url: str) -> bool:
    try:
        if sys.platform == "win32":
            # Windows 的 startfile 交給系統的預設瀏覽器，不建立會繼承 stdout 的子程序
            os.startfile(url)  # type: ignore[attr-defined]  # 只有 Windows 有這個函式
            return True
        opener = shutil.which("open" if sys.platform == "darwin" else "xdg-open")
        if opener is None:
            return False
        subprocess.Popen(
            [opener, url],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            # 獨立的 session：MCP server 結束時不會連帶關掉剛開的瀏覽器
            start_new_session=True,
        )
    except OSError:
        return False
    return True
