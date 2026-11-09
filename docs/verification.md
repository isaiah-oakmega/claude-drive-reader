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
| 三平台 CI | GitHub Actions：ubuntu、macos、windows | |

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
