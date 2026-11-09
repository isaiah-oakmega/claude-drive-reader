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
