"""Code Relay 的終點：在 127.0.0.1 上等待瀏覽器帶著 code 回來（A2、A7）。

listener 只管 HTTP：解析參數、回固定的結果頁、逾時關閉。哪個請求算數由呼叫端傳入的 handler 決定，
handler 回傳 None 代表「不算數，繼續等」，回傳 AttemptResult 代表這次授權已經有結果。
"""

import sys
import threading
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlsplit

from local_authorization.domain.attempt import AttemptResult

CallbackHandler = Callable[[dict[str, str]], AttemptResult | None]

# A7：每種結果只有一段事先寫好的訊息，頁面上絕不出現請求帶來的任何參數。
_PAGES: dict[AttemptResult | None, tuple[HTTPStatus, str, str]] = {
    AttemptResult.SUCCEEDED: (HTTPStatus.OK, "授權完成", "Drive Reader 已取得授權。請回到 Claude Code 繼續。"),
    AttemptResult.DENIED: (HTTPStatus.OK, "已拒絕授權", "你拒絕了這次授權，Drive Reader 沒有取得任何權限。"),
    AttemptResult.FAILED: (HTTPStatus.OK, "授權失敗", "這次授權沒有完成。請回到 Claude Code 重新授權。"),
    AttemptResult.TIMED_OUT: (HTTPStatus.OK, "授權已逾時", "這次授權已經逾時。請回到 Claude Code 重新授權。"),
    None: (HTTPStatus.BAD_REQUEST, "無效的請求", "這個請求不屬於進行中的授權，已忽略。"),
}
_NOT_FOUND = (HTTPStatus.NOT_FOUND, "找不到頁面", "這裡只處理授權的回傳。")
_CRASHED = (HTTPStatus.INTERNAL_SERVER_ERROR, "處理失敗", "處理這個請求時發生錯誤，授權仍在等待中。")


def _html(title: str, message: str) -> bytes:
    return (
        '<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8">'
        f"<title>Drive Reader：{title}</title></head>"
        f"<body><h1>{title}</h1><p>{message}</p></body></html>"
    ).encode("utf-8")


class _Server(ThreadingHTTPServer):
    # Windows 的 SO_REUSEADDR 允許其他程式綁同一個 port 搶走 callback，所以只在其他平台開啟
    # （在 Linux、macOS 上它只是讓固定 port 在上一次關閉後能立刻重新使用）。
    allow_reuse_address = sys.platform != "win32"
    daemon_threads = True
    # 由 LoopbackListener.serve 設定，供 _RequestHandler 使用
    handle_callback: CallbackHandler
    finish: Callable[[], None]


class LoopbackListener:
    def __init__(self, server: _Server) -> None:
        self._server = server
        self.port: int = server.server_address[1]
        self._timer: threading.Timer | None = None
        self._serving = False
        self._closed = threading.Event()
        self._lock = threading.Lock()

    @classmethod
    def bind(cls, port: int | None) -> "LoopbackListener":
        # 只綁 127.0.0.1：同一個網路上的其他機器連不到。port 0 交給 OS 分配一個沒人用的 port。
        # 先 bind 才知道實際的 port，state 要把它帶給 Broker。
        return cls(_Server(("127.0.0.1", port or 0), _RequestHandler))

    def serve(self, handle: CallbackHandler, timeout_seconds: float, on_timeout: Callable[[], None]) -> None:
        self._server.handle_callback = handle
        self._server.finish = self._finish_in_background

        def expire() -> None:
            if not self._closed.is_set():
                on_timeout()
                self.close()

        self._timer = threading.Timer(timeout_seconds, expire)
        self._timer.daemon = True
        self._timer.start()
        self._serving = True
        threading.Thread(target=self._server.serve_forever, name="loopback-listener", daemon=True).start()

    def close(self) -> None:
        with self._lock:
            if self._closed.is_set():
                return
            self._closed.set()
        if self._timer is not None:
            self._timer.cancel()
        if self._serving:
            # shutdown 會等 serve_forever 結束；從沒開始 serve 時呼叫它會永遠等下去
            self._server.shutdown()
        self._server.server_close()

    def _finish_in_background(self) -> None:
        # 由處理請求的 thread 呼叫；另開 thread 關閉，讓這個請求先把結果頁送完
        threading.Thread(target=self.close, daemon=True).start()


class _RequestHandler(BaseHTTPRequestHandler):
    server: _Server

    def do_GET(self) -> None:
        url = urlsplit(self.path)
        if url.path != "/callback":
            self._reply(*_NOT_FOUND)
            return
        # 同名參數只取第一個；值是否正確由 handler 判斷
        params: dict[str, str] = {}
        for key, value in parse_qsl(url.query, keep_blank_values=True):
            params.setdefault(key, value)
        try:
            result = self.server.handle_callback(params)
        except Exception:
            # handler 的程式錯誤不能讓 listener 停掉，否則使用者只能等 5 分鐘逾時
            self._reply(*_CRASHED)
            return
        self._reply(*_PAGES[result])
        if result is not None:
            self.server.finish()

    def _reply(self, status: HTTPStatus, title: str, message: str) -> None:
        body = _html(title, message)
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        # 結果頁不需要被快取，也不該被別的網站嵌入
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        # 預設會把完整請求行（含 ?code=…）印到 stderr，而 stderr 會進 Claude Code 的 log。一律不記。
        pass
