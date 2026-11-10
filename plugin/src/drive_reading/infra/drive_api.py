"""Google Drive API v3 的呼叫（C4）。HTTP 狀態碼只在這裡出現，往上只拋領域例外。"""

import time
from collections.abc import Callable, Iterator
from typing import Any

import httpx2

from drive_reading.domain.drive_item import DriveItem
from drive_reading.domain.errors import GoogleApiError, NotFoundOrNoAccess
from drive_reading.domain.limits import RETRY_DELAYS_SECONDS
from local_authorization.app import AccessTokenProvider

FILES_ENDPOINT = "https://www.googleapis.com/drive/v3/files"
# 只要我們用得到的欄位：回應越小越快，也不會意外拿到不需要的個人資料
ITEM_FIELDS = "id,name,mimeType,parents,size,modifiedTime,driveId,shortcutDetails(targetId,targetMimeType)"
# files.list 一頁最多 1000 筆；R3 的上限是 500，通常一頁就夠
PAGE_SIZE = 1000


class _NotFound(Exception):
    """Drive 回 404。由呼叫端決定這是 Failure（get_item）還是「看不到」（find_item）。"""


class DownloadTooLarge(Exception):
    """下載或匯出的內容超過上限（R4），已中止。"""


class ExportTooLarge(Exception):
    """Google 拒絕匯出：文件超過 Drive 的匯出大小上限（exportSizeLimitExceeded）。"""


class DriveApi:
    def __init__(self, http: httpx2.Client, tokens: AccessTokenProvider, sleep: Callable[[float], None] = time.sleep) -> None:
        self._http = http
        # C2：只需要「一個有效的 access token」，不知道也不在乎它從哪裡來
        self._tokens = tokens
        # 測試時換成記錄用的函式，不必真的等待
        self._sleep = sleep

    def get_item(self, item_id: str) -> DriveItem:
        try:
            return self._item(item_id)
        except _NotFound:
            raise NotFoundOrNoAccess(item_id) from None

    def find_item(self, item_id: str) -> DriveItem | None:
        try:
            return self._item(item_id)
        except _NotFound:
            return None

    def list_children(self, folder: DriveItem) -> Iterator[DriveItem]:
        params: dict[str, str | int] = {
            # folder.id 一定來自 Drive 的回應或 parse_drive_id，只有 ID 字元，不會跳出引號
            "q": f"'{folder.id}' in parents and trashed = false",
            "fields": f"nextPageToken,files({ITEM_FIELDS})",
            "pageSize": PAGE_SIZE,
            # 兩個都要設，才會包含共用雲端硬碟中的項目
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        if folder.drive_id:
            # 共用雲端硬碟中的資料夾，要在那個雲端硬碟的範圍內查詢
            params |= {"corpora": "drive", "driveId": folder.drive_id}
        page_token: str | None = None
        while True:
            page = self._get_json(FILES_ENDPOINT, params | ({"pageToken": page_token} if page_token else {}))
            # 逐筆交出：呼叫端達到 500 筆上限時停止迭代，就不會再要下一頁
            for data in page.get("files", []):
                yield _to_item(data)
            page_token = page.get("nextPageToken")
            if not page_token:
                return

    def download(self, item_id: str, max_bytes: int) -> bytes:
        try:
            return self._get_bytes(f"{FILES_ENDPOINT}/{item_id}", {"alt": "media", "supportsAllDrives": "true"}, max_bytes)
        except _NotFound:
            raise NotFoundOrNoAccess(item_id) from None

    def export(self, item_id: str, mime_type: str, max_bytes: int) -> bytes:
        try:
            return self._get_bytes(f"{FILES_ENDPOINT}/{item_id}/export", {"mimeType": mime_type}, max_bytes)
        except _NotFound:
            raise NotFoundOrNoAccess(item_id) from None
        except GoogleApiError as error:
            if error.reason == "exportSizeLimitExceeded":
                # R4：這是 Read Limitation，不是 Failure
                raise ExportTooLarge from error
            raise

    def _item(self, item_id: str) -> DriveItem:
        data = self._get_json(f"{FILES_ENDPOINT}/{item_id}", {"fields": ITEM_FIELDS, "supportsAllDrives": "true"})
        return _to_item(data)

    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._send(url, params)
        try:
            response.read()
            _raise_for_status(response)
            try:
                data = response.json()
            except ValueError:
                data = None
        finally:
            response.close()
        if not isinstance(data, dict):
            # 例如公司網路的 proxy 回了一個登入頁
            raise GoogleApiError(200, "回應不是 Drive API 的格式")
        return data

    def _get_bytes(self, url: str, params: dict[str, Any], max_bytes: int) -> bytes:
        response = self._send(url, params)
        try:
            if response.status_code != 200:
                response.read()
                _raise_for_status(response)
            chunks: list[bytes] = []
            received = 0
            try:
                for chunk in response.iter_bytes():
                    received += len(chunk)
                    if received > max_bytes:
                        # R4 的第二道檢查：邊收邊算，一超過就中止，不把整個大檔案收完
                        raise DownloadTooLarge
                    chunks.append(chunk)
            except httpx2.HTTPError as error:
                raise GoogleApiError(None, "下載途中連線中斷") from error
            return b"".join(chunks)
        finally:
            response.close()

    def _send(self, url: str, params: dict[str, Any]) -> httpx2.Response:
        """送出 GET 並處理重試。回傳的 response 還沒讀取 body，呼叫端負責 close。"""
        retried_auth = False
        delays = list(RETRY_DELAYS_SECONDS)
        while True:
            # 每次都重新取 token：invalidate 之後，這裡就會拿到 refresh 過的新 token。
            # NotAuthorized 等例外直接往上拋，由 mcp_server 轉成對應的 Failure。
            headers = {"Authorization": f"Bearer {self._tokens.get_access_token()}"}
            request = self._http.build_request("GET", url, params=params, headers=headers)
            try:
                # stream=True：下載時才能邊收邊檢查大小，而不是先把整個檔案讀進記憶體
                response = self._http.send(request, stream=True)
            except httpx2.HTTPError as error:
                raise GoogleApiError(None, "無法連線到 Google Drive") from error

            if response.status_code == 401 and not retried_auth:
                # access token 可能剛好過期或被撤銷：丟掉快取、refresh，只重來一次（C2）
                response.close()
                self._tokens.invalidate()
                retried_auth = True
                continue
            if (response.status_code == 429 or response.status_code >= 500) and delays:
                # R7：這裡只有讀取類的 GET（含下載與匯出），重送不會造成任何副作用
                response.close()
                self._sleep(delays.pop(0))
                continue
            return response


def _raise_for_status(response: httpx2.Response) -> None:
    if response.status_code == 404:
        raise _NotFound
    if response.status_code != 200:
        raise GoogleApiError(response.status_code, _reason(response))


def _to_item(data: dict[str, Any]) -> DriveItem:
    try:
        shortcut = data.get("shortcutDetails") or {}
        return DriveItem(
            id=data["id"],
            name=data["name"],
            mime_type=data["mimeType"],
            parents=tuple(data.get("parents", [])),
            # Drive 以字串回傳 size（可能超過 JavaScript 的整數範圍）
            size=int(data["size"]) if "size" in data else None,
            modified_time=data.get("modifiedTime"),
            drive_id=data.get("driveId"),
            shortcut_target_id=shortcut.get("targetId"),
            shortcut_target_mime_type=shortcut.get("targetMimeType"),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise GoogleApiError(200, "回應缺少必要的欄位") from error


def _reason(response: httpx2.Response) -> str:
    # Google 的錯誤格式：{"error": {"code": 403, "message": "...", "errors": [{"reason": "..."}]}}
    # reason 是穩定的短代碼（例如 insufficientFilePermissions），比 message 適合放進 Failure
    try:
        error = response.json()["error"]
        errors = error.get("errors") or [{}]
        return errors[0].get("reason") or error.get("message") or response.reason_phrase
    except (ValueError, KeyError, TypeError, AttributeError):
        return response.reason_phrase or f"HTTP {response.status_code}"
