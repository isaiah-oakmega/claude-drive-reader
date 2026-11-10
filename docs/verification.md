# 驗證紀錄

依 [實作規格](implementation-spec.md)「Verification Strategy」記錄每個階段的測試清單與結果。

- **Mock 測試**：自動執行，不連真實的 Google。結果以 CI 為準，這裡只列測試涵蓋的規則。
- **真實驗收**：手動執行，連真實的 Google OAuth 與 Drive。每筆都記錄日期、帳號類型、情境編號、結果。

帳號類型：

| 代號 | 說明 |
|---|---|
| 主帳號 | GCP 專案擁有者，在同意畫面的 Test users 名單內 |
| 第二帳號 | 模擬驗收者：不在 GCP 專案、不在 Test users |

---

## 階段 0：Repo 骨架與 CI

| 項目 | 方法 | 結果 |
|---|---|---|
| 兩個專案的套件都能 import | `tests/test_smoke.py` | ✅ 2026-11-10 本機（Linux）：backend 5 passed、plugin 9 passed |
| lockfile 與 `pyproject.toml` 一致 | `uv sync --locked` | ✅ 2026-11-10 本機 |
| 依賴規則可以執行、目前沒有違規 | `lint-imports` | ✅ 2026-11-10 本機：backend 1 kept、plugin 4 kept |
| 依賴規則確實會擋下違規 | 暫時在 `drive_reading.domain` 加入 `import local_authorization.infra` 與 `import drive_reading.app` | ✅ 2026-11-10 本機：規則 1 與分層規則 BROKEN，還原後 4 kept（正式的 CI 故意失敗測試在階段 6） |
| 三平台 CI | GitHub Actions：ubuntu、macos、windows | ✅ 2026-11-10 run #42665407626（`phase-1a-broker`，包含階段 0 全部 commit）：6 個 job 全部 success。階段 0 分支自己的 run 中，`plugin on macos-latest` 因 GitHub macOS runner 容量不足被取消，測試從未執行，不是失敗 |

## 階段 1a：Token Broker（Mock 測試）

不連網：Google 以 `httpx.MockTransport` 取代，HTTP 端點以 FastAPI `TestClient` 測試。2026-11-10 本機（Linux）共 96 passed；import-linter 1 kept。

| 規則 | 測試 | 結果 |
|---|---|---|
| B1 應用程式 log 只有方法、路徑、狀態碼 | `tests/api/test_routes.py::test_logs_contain_only_method_path_and_status`：送出含 code、refresh token、verifier 的請求，log 中不得出現這些值、client secret 或 `?` | ✅ |
| B1 容器內 uvicorn 不記 access log | 本機 `docker run` 後請求 `/callback?code=…`，`docker logs` 只出現 `GET /callback 302`，code 出現 0 次 | ✅ |
| B2 只轉到 `127.0.0.1:<port>/callback` | `tests/domain/test_code_relay.py`：`tests/contract/state_vectors.json` 的 5 個合法、18 個不合法向量（前導零、全形數字、host 注入、路徑、換行、標記等）；`test_callback_with_bad_state_never_redirects` | ✅ |
| B3 `/token` 只接受兩種形狀 | `tests/domain/test_token_grant.py`；`test_other_token_shapes_get_422_and_never_reach_google`（422 且沒有送出任何 Google 請求） | ✅ |
| B4 scope 固定為 `drive.readonly` | `test_authorization_url_has_exactly_the_fixed_parameters`；`test_authorize_ignores_scope_supplied_by_caller`；多送 `scope` 欄位的 `/token` 請求回 422 | ✅ |
| B5 `redirect_uri` 只有一個來源 | `test_code_exchange_sends_secret_verifier_and_redirect_uri`；`tests/test_settings.py::test_redirect_uri_is_derived_from_public_base_url` | ✅ |
| B6 錯誤頁不回顯參數 | `test_error_pages_do_not_reflect_input`：在 `state`、`code_challenge`、`error` 塞入 `<script>`、`<img onerror>` | ✅ |
| C1 各端點的狀態碼與回應形狀 | `tests/api/test_routes.py`：`/authorize` 302 與 400、`/callback` 302 與 400、`/token` 200（含 `Cache-Control: no-store`）、400 透傳、502、422、`/`、`/privacy`、`/healthz`；`/docs`、`/redoc`、`/openapi.json` 為 404 | ✅ |
| 上游錯誤的對應 | `tests/infra/test_google_oauth.py`：Google 400 `invalid_grant` 透傳；500、503、429、非 JSON、格式不符的 200、連線失敗、逾時都轉成「上游無法使用」 | ✅ |
| C5 缺設定時啟動失敗、不洩漏值 | `tests/test_settings.py`；本機 `docker run` 不帶環境變數時輸出 `MissingSettings`，只列變數名稱 | ✅ |
| Docker 映像檔可建置 | `docker build`（`uv sync --locked --no-dev`） | ✅ |
| 三平台 CI | run #42665407626：backend 與 plugin × ubuntu、macos、windows | ✅ 6/6 success |

## 階段 1b：Broker 部署與真實驗證

部署在 Cloud Run `asia-east1`，服務名稱 `token-broker`，自訂網域 `https://drive-auth.isaiahlin.dev`。

### 部署設定

| 項目 | 結果 |
|---|---|
| 啟用的 API | Run、Cloud Build、Artifact Registry、Secret Manager、Drive、Logging、IAM |
| 風險 #3：網域擁有權與 region 支援 domain mapping | ✅ 2026-11-10 `gcloud domains list-user-verified` 列出 `isaiahlin.dev`；`asia-east1` 可建立 domain mapping |
| 執行用的 service account | 專用的 `token-broker@…`，只對 `google-oauth-client-secret` 這一個 secret 有 `secretAccessor` |
| 從原始碼建置的權限 | 第一次 `gcloud run deploy --source` 因預設 compute service account 沒有建置權限而失敗；給它 `roles/run.builder` 後成功。只影響建置，執行時仍用上面的專用 service account |
| 規模 | `--min-instances 0 --max-instances 2`，沒有流量時不計費 |
| 設定來源 | `GOOGLE_CLIENT_ID`、`PUBLIC_BASE_URL` 為環境變數；`GOOGLE_CLIENT_SECRET` 從 Secret Manager 掛入，不出現在部署指令或 revision 設定的明文中 |

### B1：平台層的 log 排除

應用程式自己不記 query string（階段 1a 已驗證），但 Cloud Run 平台的 request log 會記下完整網址，包含 `/callback?code=…`。因此在 `_Default` sink 加上排除規則 `exclude-broker-callback`：

```
resource.type="cloud_run_revision" AND resource.labels.service_name="token-broker" AND httpRequest.requestUrl:"/callback"
```

| 探測 | 送出時間（UTC） | 是否被記錄 |
|---|---|---|
| `/callback?code=x…`（規則剛建立） | 2026-11-09 17:45 | 有 |
| `/callback?code=EXCLUSION-PROBE-2…` | 17:48 | 有（同時送出的對照請求也有，確認 filter 能比對到這些記錄） |
| `/callback?code=EXCLUSION-PROBE-3…` | 17:51 | **沒有** ✅ |

觀察：排除規則建立後約 5 分鐘才生效。被記下的三筆都是假的 code，不是真實授權碼。重建步驟要寫明「先設定排除規則、等 5 分鐘，再做第一次真實授權」。

### 規格修正：健康檢查改為 `/health`

部署後 `GET /healthz` 回的是 Google 前端自己的 404，請求根本沒進到容器：Cloud Run 保留結尾是 `z` 的路徑。經同意後把 C1 改成 `GET /health`（規格與程式各一個 commit）。重新部署為 revision `token-broker-00002-ds5` 後，`/health` 回 200 `ok`；service account 與 `max-instances` 沿用原設定。

部署時的一次失敗：重新部署時上傳的是整個 repo 根目錄，而不是 `backend/`。根目錄沒有 Dockerfile，Cloud Build 就改用 buildpacks 自動判斷，因為找不到程式進入點而失敗，線上的舊 revision 不受影響。部署指令一律在 repo 根目錄執行，並明確指定 `--source backend`。

### 真實驗收

| 項目 | 帳號 | 結果 |
|---|---|---|
| `*.run.app` 上的端點：`/`、`/privacy` 200；`/docs` 404；`/authorize` 302 到 Google；不合法的 `/callback` 400；形狀不合的 `/token` 422 | — | ✅ 2026-11-10 |
| 假的 refresh token 經 Broker 送到真實 Google，Google 的錯誤原樣轉回 | — | ✅ 2026-11-10：400 `{"error":"invalid_grant","error_description":"Bad Request"}` |
| 自訂網域的憑證 | — | ✅ 2026-11-10：Cloudflare 加上 CNAME（DNS only）後約 1 小時簽發，`CN=drive-auth.isaiahlin.dev`，簽發者 Google Trust Services，之後由 Google 自動續期 |
| 自訂網域上的端點：`/health` 200、`/`、`/privacy` 200、`/docs` 404、不合法的 `/callback` 400、`/authorize` 302 且 `redirect_uri` 是自訂網域的 `/callback` | — | ✅ 2026-11-10 |
| 真實授權的 Code Relay：`/authorize` → Google 同意畫面（Testing 狀態）→ Broker `/callback` 302 → 瀏覽器轉到 `127.0.0.1:53682/callback`，本機沒有 listener，顯示 `ERR_CONNECTION_REFUSED`（預期） | 主帳號 | ✅ 2026-11-10 10:53 UTC：`/authorize` 302 後 12 秒 Broker 收到 `/callback` 並回 302 |
| B1：真實授權碼經過後，Cloud Logging 沒有留下 code | 主帳號 | ✅ 2026-11-10：平台 request log 中 `/callback` 0 筆（排除規則生效）；應用程式 log 只有 `GET /callback 302`；30 分鐘內含 `code=` 或 `4/0` 的記錄 0 筆 |
| 對照：同意畫面還在 Testing 時，不在 Test users 名單的帳號 | 第二帳號 | 預期中的封鎖（2026-11-10 10:54 UTC）：「已封鎖存取權：未完成 Google 驗證程序……目前處於測試階段」，`Error 403: access_denied`，沒有繼續的選項，也沒有呼叫 `/callback`。所以驗收者用的 app **一定要先 Publish** |
| **風險 #2**：Publish app（In production、不送驗證）後，陌生帳號看到的是可以繼續的未驗證警告，而不是封鎖 | 第二帳號 | ✅ 2026-11-10 10:57 UTC：出現「Google 尚未驗證這個應用程式」，點「進階」→「前往（不安全）」→ 同意 → Broker `/callback` 302 → 瀏覽器轉到 `127.0.0.1:53682`（`ERR_CONNECTION_REFUSED`，預期）。整條 OAuth 路線成立 |
| B1：第二帳號授權後 | 第二帳號 | ✅ 2026-11-10：2 小時內平台 request log 中 `/callback` 0 筆；含 `code=` 或 `4/0` 的記錄 0 筆 |

觀察：
- 未驗證的 app 在 Google 的畫面上顯示的是網域 `isaiahlin.dev`，不是設定的 app 名稱。README 的警告畫面說明要照實際畫面寫。
- 發布之後，Testing 狀態下「refresh token 7 天失效」的限制就不再適用（計畫的 X2）。發布前取得的 credential 需要重新授權。

| 項目 | 方法 | 結果 |
|---|---|---|
| 三平台 CI | GitHub Actions run #42803651798（`main` 的 `e573e1f`，含 `/health` 修正） | ✅ 6/6 success |

## 階段 2：Plugin 骨架與 Local Authorization

### Spike（本階段最先做）

暫時性的 `spike_image` tool 回傳一張 96×48 的 PNG，由三條直條組成。顏色故意不寫在 tool 描述裡，模型只能從圖片本身得知。spike 的程式在階段 2 結束前移除。

| 風險 | 方法 | 結果 |
|---|---|---|
| #8：從 GitHub 安裝子目錄 `./plugin` | `claude plugin marketplace add isaiah-oakmega/claude-drive-reader#phase-2-local-auth`，再 `claude plugin install drive-reader@drive-reader-marketplace` | ✅ 2026-11-10 Linux，Claude Code 2.1.317：repo 還是 private，Claude Code 先確認 SSH key 可用，改用 SSH clone；marketplace 加入成功，plugin 裝在 user scope 且為 enabled。從安裝後的副本（`~/.claude/plugins/cache/…`）啟動 MCP server，1.4 秒完成握手 |
| #1：MCP tool 回傳的圖片會交給模型 | 在新的 Claude Code session（Desktop 的 Code tab）要求呼叫 `spike_image` 並說出顏色 | ✅ 2026-11-10：模型回答由左到右為黃、黑、洋紅，和圖片一致 |
| #4：`uv run --frozen` 第一次啟動的耗時 | 暫時的握手腳本照 `.mcp.json` 啟動 MCP server，量從啟動子程序到 `initialize` 完成的時間。冷：uv 快取與 Python 安裝目錄都指向全新的空目錄；熱：用現有的快取 | 2026-11-10 Linux：冷啟動 4.2 秒（含下載約 104MB 的 Python 3.12 與 29 個套件，實際時間取決於頻寬），熱啟動 1.2 秒。Windows 的數字在煙霧測試時補上 |

觀察：
- Claude Desktop 的 Code tab 沒有 `/plugin` 指令，改用 prompt 框旁的 **+** → **Add plugins** 開 plugin 瀏覽器，但它只列出已經加入的 marketplace，不能從 GitHub 加入新的 marketplace。同一台電腦上的 Desktop 和終端機版共用同一份設定檔，所以在終端機執行 `claude plugin marketplace add` 與 `claude plugin install` 後，Desktop 新開的 session 就會載入。README 要寫明這一點。
- plugin 只在 session 啟動時載入，裝好後要開新的 session。

### Mock 測試

不連網：Broker 與 Google 以 `httpx2.MockTransport` 取代；loopback listener 真的在 127.0.0.1 開 port，用 HTTP client 打它；credential 檔寫在 `tmp_path`。2026-11-10 本機（Linux）共 197 passed；import-linter 4 kept。

| 規則 | 測試 | 結果 |
|---|---|---|
| C1 `state` 格式（規則 5） | `tests/contract/test_state_format.py`：和 backend 同一份 `state_vectors.json`（另有一條測試確認兩份檔案內容相同）；本機產生的 `state` 一定符合 Broker 的格式；port 超出 1024–65535 時拒絕產生 | ✅ |
| A1 同時最多一個 Attempt | `test_new_authorize_closes_and_replaces_previous_attempt`：舊的 listener 關閉，帶舊 `state` 的 callback 不算數 | ✅ |
| A2 一次性、5 分鐘逾時、`state` 常數時間比對 | `tests/local_authorization/domain/test_attempt.py`：注入時間測逾時；收到 code 後不再接受任何 callback；非 ASCII 的 `state` 不會讓比對拋例外 | ✅ |
| A2 `state` 不符回 400 且**不結束** Attempt | domain 的 `test_request_without_matching_state_is_rejected_and_attempt_keeps_waiting`（5 種雜訊請求之後，有效的 callback 仍能完成）；listener 的 `test_rejected_request_gets_400_and_listener_keeps_waiting`；`test_authorization_flow.py` 以真實 listener 走完「雜訊 400 → 有效 callback 200」 | ✅ |
| 使用者拒絕、Google 其他錯誤、換 code 失敗 | `access_denied` → 已拒絕；其他 `error` 與 Broker 失敗、沒有 refresh token → 失敗；三者都不動既有的 Local Credential | ✅ |
| 逾時關閉 listener | listener 的 `test_timeout_calls_back_and_closes_listener`；service 的 `test_listener_timeout_is_reported_as_timed_out`，以及計時器還沒觸發時 `auth_status` 也以時間判定逾時 | ✅ |
| `DRIVE_READER_CALLBACK_PORT` 固定 port | `test_fixed_port_is_used_when_configured`、`test_configured_callback_port_is_used`；port 被占用時回報 `CALLBACK_PORT_UNAVAILABLE`（規格經同意後新增的代碼）；設定值不是 1024–65535 的 ASCII 整數時啟動失敗（含全形數字） | ✅ |
| A3 只保存 refresh token | `test_local_credential_holds_only_refresh_token_scope_and_time`、`test_file_contains_only_the_credential_fields` | ✅ |
| A4 權限與原子寫入 | `test_file_is_0600_and_new_directory_is_0700`、umask 為 0 時覆寫仍是 0600、不改使用者指定的既有目錄權限、`os.replace` 失敗時舊檔完整且沒有殘留暫存檔。Windows 上權限測試 skip，改為驗證 `permissions_enforced` 為 False，`auth_status` 不宣稱 0600 | ✅ |
| A5 `invalid_grant` 時刪除 | `test_invalid_grant_deletes_credential`：刪檔後下一次呼叫是 `NotAuthorized` | ✅ |
| A6 logout | 先 revoke 再刪除；revoke 失敗仍刪除並回報，附上手動移除存取權的網址；沒有授權時不呼叫 Google | ✅ |
| A7 結果頁不回顯參數 | `test_result_pages_never_reflect_request_parameters`：每種結果頁都送入 `<script>`；另確認請求行（含 `code`）不會被印到 stdout 或 stderr | ✅ |
| C2 refresh 時機與 `invalidate` | 到期前 60 秒內才 refresh；`invalidate` 後強制 refresh；授權完成時直接使用換 code 拿到的 access token；Google 換發新的 refresh token 才寫檔 | ✅ |
| C2 `current_account` | 只查一次並快取；未授權或 Broker 失敗時回 None；重新授權或 logout 後重新查詢 | ✅ |
| C1 消費端 | `test_broker_client.py`：兩種 `/token` 請求的 JSON 形狀；`invalid_grant` → `AuthExpired`；其他 400、422、5xx、404、非 JSON、欄位缺漏或型別錯誤、連線失敗、逾時 → `BrokerUnreachable` 並附網址；換 code 不重試 | ✅ |
| C3 授權相關 tool | `test_tools.py`：三個 tool 沒有必填參數、描述有中文；`authorize` 回傳網址、未驗證警告的操作與「完成後告訴我」；`auth_status` 四種上一次結果；Failure 格式 `[代碼] 原因。下一步：…` | ✅ |
| 打包與啟動 | `test_stdio_server.py`：以 `python -m mcp_server` 透過 stdio 握手，列出三個 tool，且不建立 credential 檔；設定錯誤時以非 0 結束，訊息只寫到 stderr | ✅ |
| 開瀏覽器不污染 MCP 的 stdout | `test_browser.py`：子程序的 stdin、stdout、stderr 都導到 DEVNULL；找不到開啟程式或啟動失敗時回 False | ✅ |
| 三平台 CI | GitHub Actions run #42827892715（`phase-2-local-auth` 的 `eba44f9`）：backend 與 plugin × ubuntu、macos、windows | ✅ 6/6 success |
| 三平台 CI（`CALLBACK_PORT_UNAVAILABLE` 修改後） | run #42830167756（`58dbcde`） | ✅ 6/6 success |
| 三平台 CI（合併進 `main` 後） | run #42843448432（`main` 的 `54aa435`） | ✅ 6/6 success |

### 真實驗收

plugin 從 GitHub 的 `phase-2-local-auth` 安裝（`dde4655`），連線正式的 Broker 與 Google。授權相關的 tool 在 Claude Code 中以自然語言觸發（「幫我授權 Google Drive」「授權狀態如何？」「登出」）。

| 項目 | 平台 | 帳號 | 結果 |
|---|---|---|---|
| 情境 1：首次授權。`authorize` 回傳網址並自動開啟瀏覽器 → 未驗證警告 → 同意 → 本機頁面「授權完成」→ `auth_status` 顯示已授權、正確的 email、上一次結果「成功」 | Linux（Claude Desktop 的 Code tab） | 主帳號 | ✅ 2026-11-10 |
| 情境 3：在 Google 同意頁面按「取消」→ 本機頁面「已拒絕授權」→ `auth_status` 上一次結果「已拒絕」，原本的授權仍在 | Linux | 主帳號 | ✅ 2026-11-10 |
| 情境 15：`logout` 回報已向 Google 撤銷、本機授權已刪除 → `auth_status` 顯示尚未授權 | Linux | 主帳號 | ✅ 2026-11-10 |
| Production 狀態下用第二帳號完成授權，`auth_status` 顯示第二帳號的 email | Linux | 第二帳號 | ✅ 2026-11-10 |
| 情境 4：開始授權後不完成，5 分鐘後 `auth_status` 顯示沒有進行中的授權、上一次結果「逾時」 | Linux | — | ✅ 2026-11-10 |
| A4：真實授權後的 `credentials.json` 權限為 `0600`、目錄為 `0700`，檔案只有 `refresh_token`、`scope`、`obtained_at` | Linux | 主帳號 | ✅ 2026-11-10 15:20 UTC：檔案 `600`、目錄 `700`、擁有者為使用者本人；欄位只有這三個，scope 為 `drive.readonly`，沒有 access token。檢查時只看欄位名稱與格式，不印出 token |
| Windows 煙霧測試：PowerShell 安裝 uv 與 Claude Code → `claude plugin install drive-reader --marketplace "isaiah-oakmega/claude-drive-reader#phase-2-local-auth"` → `/mcp` 數秒內 connected → 授權成功，`auth_status` 顯示正確的 email，授權保存在 `C:\Users\<使用者>\.config\claude-drive-reader\credentials.json` | Windows（Claude Code CLI） | 主帳號 | ✅ 2026-11-10 |

觀察：
- Windows 上的 Claude Code CLI 安裝程式不會自己修改 PATH。uv 的安裝程式會把同一個 `%USERPROFILE%\.local\bin` 加進使用者 PATH，所以先裝 uv 再裝 Claude Code 時，不需要另外設定。README 的 Windows 步驟要寫明這個順序，並附上 PATH 沒設定時的處理方式。
- Claude 會把 tool 的回傳整理成摘要再呈現，不一定逐字顯示。Windows 上 `auth_status` 對檔案保護方式的描述（不宣稱 0600）由 mock 測試涵蓋，CI 的 Windows job 也有跑。
- 階段 2 結束時移除了暫時的 `spike_image` tool；stdio 握手測試改為確認只提供 `authorize`、`auth_status`、`logout` 三個 tool。

## 階段 3：Drive Reading——存取與列出

### Mock 測試

不連網：Drive API 以 `httpx2.MockTransport` 取代；use case 與 tool 用記憶體裡的假 Drive（`tests/support/drive_fakes.py`，一棵含子資料夾、捷徑、Root Folder 外資料夾的樹）。2026-11-10 本機（Linux）plugin 共 285 passed；import-linter 4 kept。

| 規則 | 測試 | 結果 |
|---|---|---|
| ID 或網址統一成 ID | `test_drive_id.py`：資料夾、檔案、文件、試算表、簡報、`open?id=`、`uc?id=` 等 11 種寫法；其他網站的網址、含引號的字串（避免改寫 `files.list` 的查詢條件）、路徑一律視為找不到 | ✅ |
| R1 Root Folder 邊界 | `test_root_folder.py`：剛好 20 層可以、21 層不行；Root Folder 外、沒有 parents、中間有看不到的祖先、共用雲端硬碟的根都視為範圍外；parents 循環不會無限查詢 | ✅ |
| R1 套用在指定的資料夾 | `test_list_files.py`：Root Folder 外的資料夾回 `OutsideRoot`，而且完全沒有列出它的內容；捷徑的目標在 Root Folder 外時同樣拒絕 | ✅ |
| R2 捷徑 | 列出時不展開，輸出標示目標 ID 與類型 | ✅ |
| R3 深度、筆數、循環、分頁 | `test_listing.py`：最多 5 層並註明沒展開的資料夾；剛好 500 筆不算截斷，第 501 筆出現才截斷，並且之後不再讀資料；廣度優先，截斷時保留淺層；重複的資料夾只展開一次。`test_drive_api.py`：跟隨 `nextPageToken`，而且只在需要時才要下一頁 | ✅ |
| 共用雲端硬碟 | `supportsAllDrives`、`includeItemsFromAllDrives`；資料夾在共用雲端硬碟中時加上 `corpora=drive`、`driveId` | ✅ |
| 404 與 401 的對應 | 404 → `NotFoundOrNoAccess`（R1 追溯祖先時則是「看不到」）；401 → `invalidate` 後換新 token 重來一次，第二次 401 → `GoogleApiError`；`NotAuthorized` 原樣往上，一個請求都不送 | ✅ |
| R7 重試 | 429、500、503 等 1 秒、2 秒後各重試一次；第三次仍失敗 → `GoogleApiError`；400、403 不重試並保留 Google 的 reason；連線失敗、非 JSON 的 200 → `GoogleApiError` | ✅ |
| R6 與 C3 的 Failure | `NOT_FOUND_OR_NO_ACCESS` 附上目前帳號的 email，下一步提到接受邀請與 logout；查 email 只在這種情況才做；`OUTSIDE_ROOT` 的下一步只導回 `list_files`，不提供繞過的方法；`GOOGLE_API_ERROR` 附狀態碼與 reason | ✅ |
| C3 `list_files` | `test_list_files_tool.py`：`folder`、`recursive` 兩個選填參數；每行為「路徑 \| 類型 \| 大小 \| 修改時間 \| ID」；空資料夾、只列直接子項目、截斷、沒展開的資料夾都有說明；名稱中的 `\|` 不會打亂欄位 | ✅ |
| C5 Root Folder 設定 | 網址在啟動時解析成 ID；不是 Drive 的 ID 或網址時啟動失敗並指出變數名稱 | ✅ |

### 真實檢查（開發者自行執行）

使用者同意後，由開發者在 Linux 上用已保存的主帳號授權（`drive.readonly`）自行檢查，範圍只限開發用資料夾。方法：用 MCP client 依 `.mcp.json` 啟動已安裝的 plugin（`phase-3-listing` 的 `89b8e62`），直接呼叫 tool。這條路徑經過正式的 Broker 與 Drive API，只有「模型依自然語言選擇 tool」這一段不在內：桌面版內建的 `claude` 沒有登入 CLI，無法以 `claude -p` 非互動執行。這一段留給使用者在 Windows 上驗收。

| 項目 | 結果 |
|---|---|
| `auth_status`：經 Broker refresh、再以 `about.get` 取得 email | ✅ 2026-11-10：已授權、主帳號 email、檔案權限 0600 |
| `list_files` 不帶參數：列出開發用資料夾 | ✅ 2026-11-10：Root Folder 名稱正確；2 個檔案（PDF、PNG），路徑、mimeType、大小、修改時間、ID 都和 Drive 一致 |
| `list_files` 指定檔案的 ID | ✅ 只列出該檔案，並說明它不是資料夾 |
| `list_files` 的 `recursive=false` | ✅ 說明「只列出直接的子項目」 |
| 情境 11：列出主帳號沒有權限的資料夾（出題方的資料夾） | ✅ `NOT_FOUND_OR_NO_ACCESS`，附上主帳號 email 與「接受邀請，或 logout 換帳號」 |
| 情境 11：Root Folder 本身沒有權限（不設定 `DRIVE_READER_ROOT_FOLDER`，使用預設的出題方資料夾） | ✅ 同上，在列出任何內容之前就回報 |

發現並修正：MCP SDK 把 log 設在 INFO，`httpx2` 因此把每個請求的完整網址（Drive 的檔案 ID 與查詢條件）寫到 stderr，而 stderr 會進 Claude Code 的 log。網址裡沒有 token，但沒有必要留下，已在組裝時把 `httpx2` 的 log 調到 WARNING（`6a42806`），重新檢查後不再出現。

## Repo 提前公開：歷史掃描

2026-11-10 repo 提前改成 public（原計畫在階段 8），讓 Windows 測試從 GitHub 安裝時不必另外設定 GitHub 登入。公開後立即掃描所有分支的完整歷史（32 個 commit）：

| 項目 | 方法 | 結果 |
|---|---|---|
| secret 與 token | 在所有 commit 的 diff 中搜尋 Google client secret（`GOCSPX`）、access token（`ya29.`）、refresh token（`1//0`）、授權碼（`4/0`）、私鑰、GitHub token 的格式 | ✅ 沒有真實值。命中的只有 `uv.lock` 套件網址中的雜湊值與測試用的假值 |
| 個人資料 | 搜尋每個 commit 的檔案內容中的 email、OAuth Client ID、GCP 專案名稱、開發用資料夾 ID | ✅ 只有範例 email（`example.com` 等） |
| commit 的作者資訊 | `git log --all --format='%ae %ce'` | commit 的作者與提交者 email 是開發者的個人信箱。改寫歷史會讓所有 commit hash 改變，本文件與 CI 紀錄引用的 commit 對不上，對作業沒有好處，因此保留 |

階段 8 交付前，會再掃描這之後新增的 commit。

## 待使用者驗收（集中進行）

開發期間需要使用者本人操作的項目先跳過，記在這裡，最後在 Windows 上集中驗收。完成的項目移到各階段的「真實驗收」表格。

### 準備：開發用資料夾的內容

- [ ] 新增一個子資料夾，裡面至少放一個檔案（階段 3 的「列出子資料夾」）
- [ ] 新增一個捷徑，指向 Root Folder 外、但帳號看得到的檔案（R2）

### 階段 3：列出

- [ ] Windows：說「列出資料夾內的檔案」，Claude 呼叫 `list_files` 並列出開發用資料夾（情境 8 的列出部分）
- [ ] Windows：說「列出〇〇子資料夾裡的檔案」，只列出該子資料夾
- [ ] Windows：列出 Root Folder 外、帳號看得到的資料夾網址，得到 `OUTSIDE_ROOT`
