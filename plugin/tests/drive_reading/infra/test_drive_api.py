"""C4 的 Drive API 呼叫：請求參數、分頁、共用雲端硬碟、401 重來一次、404、R7 的重試。"""

import httpx2
import pytest

from drive_reading.domain.drive_item import FOLDER_MIME, SHORTCUT_MIME, DriveItem
from drive_reading.domain.errors import GoogleApiError, NotFoundOrNoAccess
from drive_reading.infra.drive_api import DriveApi
from local_authorization.app import NotAuthorized

FOLDER = DriveItem(id="folder-id", name="Root", mime_type=FOLDER_MIME)
FILE_JSON = {
    "id": "file-id",
    "name": "memo.pdf",
    "mimeType": "application/pdf",
    "parents": ["folder-id"],
    "size": "2048",
    "modifiedTime": "2026-11-01T10:00:00.000Z",
}


class FakeTokens:
    def __init__(self) -> None:
        self.issued = 0
        self.invalidated = 0
        self.error: Exception | None = None

    def get_access_token(self) -> str:
        if self.error is not None:
            raise self.error
        self.issued += 1
        return f"ya29.{self.issued}"

    def invalidate(self) -> None:
        self.invalidated += 1


class FakeDrive:
    def __init__(self, *responses) -> None:
        # 依序回傳；最後一個會一直重複使用
        self.responses = list(responses)
        self.requests: list[httpx2.Request] = []

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        answer = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


def api_for(drive: FakeDrive, tokens: FakeTokens | None = None, sleeps: list[float] | None = None) -> DriveApi:
    record = sleeps if sleeps is not None else []
    return DriveApi(httpx2.Client(transport=httpx2.MockTransport(drive.handler)), tokens or FakeTokens(), sleep=record.append)


# ---------- files.get ----------


def test_get_item_requests_metadata_with_bearer_token() -> None:
    drive = FakeDrive(httpx2.Response(200, json=FILE_JSON))

    item = api_for(drive).get_item("file-id")

    request = drive.requests[0]
    assert str(request.url).startswith("https://www.googleapis.com/drive/v3/files/file-id?")
    assert request.headers["authorization"] == "Bearer ya29.1"
    assert request.url.params["supportsAllDrives"] == "true"
    assert "parents" in request.url.params["fields"] and "shortcutDetails" in request.url.params["fields"]
    assert item == DriveItem(
        id="file-id",
        name="memo.pdf",
        mime_type="application/pdf",
        parents=("folder-id",),
        size=2048,
        modified_time="2026-11-01T10:00:00.000Z",
    )


def test_shortcut_details_are_parsed() -> None:
    shortcut = {"id": "s", "name": "捷徑", "mimeType": SHORTCUT_MIME, "shortcutDetails": {"targetId": "t", "targetMimeType": "application/pdf"}}

    item = api_for(FakeDrive(httpx2.Response(200, json=shortcut))).get_item("s")

    assert (item.shortcut_target_id, item.shortcut_target_mime_type) == ("t", "application/pdf")


def test_404_means_not_found_or_no_access() -> None:
    drive = FakeDrive(httpx2.Response(404, json={"error": {"code": 404, "message": "File not found: x."}}))

    with pytest.raises(NotFoundOrNoAccess) as raised:
        api_for(drive).get_item("missing-id")
    assert raised.value.reference == "missing-id"


def test_find_item_returns_none_on_404() -> None:
    # R1 往上追溯時，看不到的祖先不是錯誤，而是「無法證明在 Root Folder 內」
    assert api_for(FakeDrive(httpx2.Response(404))).find_item("hidden") is None


# ---------- files.list ----------


def test_list_children_queries_folder_and_follows_pages() -> None:
    page1 = {"files": [FILE_JSON | {"id": "a", "name": "a"}], "nextPageToken": "next"}
    page2 = {"files": [FILE_JSON | {"id": "b", "name": "b"}]}
    drive = FakeDrive(httpx2.Response(200, json=page1), httpx2.Response(200, json=page2))

    items = list(api_for(drive).list_children(FOLDER))

    assert [item.id for item in items] == ["a", "b"]
    first, second = drive.requests
    assert first.url.params["q"] == "'folder-id' in parents and trashed = false"
    assert first.url.params["supportsAllDrives"] == "true"
    assert first.url.params["includeItemsFromAllDrives"] == "true"
    assert "pageToken" not in first.url.params
    assert second.url.params["pageToken"] == "next"


def test_shared_drive_folder_is_listed_within_that_drive() -> None:
    drive = FakeDrive(httpx2.Response(200, json={"files": []}))
    shared = DriveItem(id="folder-id", name="Team", mime_type=FOLDER_MIME, drive_id="drive-123")

    list(api_for(drive).list_children(shared))

    params = drive.requests[0].url.params
    assert (params["corpora"], params["driveId"]) == ("drive", "drive-123")


def test_pages_are_fetched_only_as_needed() -> None:
    page = {"files": [FILE_JSON], "nextPageToken": "more"}
    drive = FakeDrive(httpx2.Response(200, json=page))

    children = api_for(drive).list_children(FOLDER)
    next(children)

    # 呼叫端只拿了一筆：不應該先把所有分頁都抓下來（R3 截斷時省下 API 呼叫）
    assert len(drive.requests) == 1


# ---------- 401：invalidate 後最多重來一次 ----------


def test_401_invalidates_token_and_retries_once() -> None:
    tokens = FakeTokens()
    drive = FakeDrive(httpx2.Response(401), httpx2.Response(200, json=FILE_JSON))

    api_for(drive, tokens).get_item("file-id")

    assert tokens.invalidated == 1
    assert [request.headers["authorization"] for request in drive.requests] == ["Bearer ya29.1", "Bearer ya29.2"]


def test_second_401_is_a_google_api_error() -> None:
    tokens = FakeTokens()
    drive = FakeDrive(httpx2.Response(401))

    with pytest.raises(GoogleApiError) as raised:
        api_for(drive, tokens).get_item("file-id")
    assert raised.value.status == 401
    assert len(drive.requests) == 2


def test_authorization_errors_propagate_without_any_request() -> None:
    # drive_reading 不攔截 Local Authorization 的例外，讓 NOT_AUTHORIZED 原樣往上（實作規格「傳遞」）
    tokens = FakeTokens()
    tokens.error = NotAuthorized()
    drive = FakeDrive(httpx2.Response(200, json=FILE_JSON))

    with pytest.raises(NotAuthorized):
        api_for(drive, tokens).get_item("file-id")
    assert drive.requests == []


# ---------- R7：429 與 5xx 退避重試 2 次 ----------


@pytest.mark.parametrize("status", [429, 500, 503])
def test_transient_errors_are_retried_with_backoff(status: int) -> None:
    sleeps: list[float] = []
    drive = FakeDrive(httpx2.Response(status), httpx2.Response(status), httpx2.Response(200, json=FILE_JSON))

    item = api_for(drive, sleeps=sleeps).get_item("file-id")

    assert item.id == "file-id"
    assert sleeps == [1.0, 2.0]


def test_gives_up_after_two_retries() -> None:
    sleeps: list[float] = []
    drive = FakeDrive(httpx2.Response(503))

    with pytest.raises(GoogleApiError) as raised:
        api_for(drive, sleeps=sleeps).get_item("file-id")
    assert raised.value.status == 503
    assert len(drive.requests) == 3
    assert sleeps == [1.0, 2.0]


@pytest.mark.parametrize("status", [400, 403])
def test_other_errors_are_not_retried_and_keep_google_reason(status: int) -> None:
    body = {"error": {"code": status, "message": "The user does not have sufficient permissions.", "errors": [{"reason": "insufficientFilePermissions"}]}}
    drive = FakeDrive(httpx2.Response(status, json=body))

    with pytest.raises(GoogleApiError) as raised:
        api_for(drive).get_item("file-id")
    assert (raised.value.status, raised.value.reason) == (status, "insufficientFilePermissions")
    assert len(drive.requests) == 1


def test_connection_failure_is_a_google_api_error() -> None:
    drive = FakeDrive(httpx2.ConnectError("offline"))

    with pytest.raises(GoogleApiError) as raised:
        api_for(drive).get_item("file-id")
    assert raised.value.status is None


def test_malformed_success_response_is_a_google_api_error() -> None:
    drive = FakeDrive(httpx2.Response(200, text="<html>proxy login</html>"))

    with pytest.raises(GoogleApiError):
        api_for(drive).get_item("file-id")
