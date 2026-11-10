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
