# 08 實作考量與風險 [推論]

> 本文件**全部不是原文要求**，而是為了滿足原文要求（尤其是「驗收者在自己環境用自己帳號跑通」）而必須注意的技術細節。實作前應再以 Google 官方文件確認最新規則。

## OAuth 同意畫面發布狀態

這是**最可能導致驗收失敗**的點。

- OAuth consent screen 若為 **Testing** 狀態：
  - 只有列在「Test users」名單中的帳號能授權 → 驗收者的帳號不在名單內就會被擋。
  - Refresh token 約 **7 天**後失效 → 交付後一週才驗收就會壞。
- 若為 **In production** 且使用 sensitive／restricted scope（Drive 讀取 scope 屬此類）而未通過驗證：
  - 使用者會看到「Google 尚未驗證這個應用程式」警告，需點「進階」→「前往（不安全）」才能繼續。
  - 未驗證應用有使用者數上限。
- 對策（擇一並寫入 README）：
  - 發布為 production，並在 README 明確說明會看到未驗證警告及如何繼續。
  - 或維持 Testing，請出題方提供驗收帳號 email 加入 test users，並說明 7 天限制。
  - 同時提供「自行申請 OAuth Client」的完整步驟作為後備路徑。

## OAuth Scope 選擇

| Scope | 適用性 |
|------|------|
| `drive.readonly` | 可讀取使用者能存取的所有檔案（含別人分享的資料夾）。符合需求，但屬 restricted scope。 |
| `drive.metadata.readonly` | 只能列出不能讀內容，不足。 |
| `drive.file` | 只能存取 app 建立或使用者透過 Picker 選取的檔案，**無法**直接存取被分享的資料夾，不適用（除非搭配 Google Picker）。 |

- 原則：只要求唯讀 scope，不要要求寫入權限。
- 選擇理由應寫進架構說明。

## OAuth Flow 選擇

需在架構說明中交代選擇理由與 trade-off，可能的方案：

- **Authorization Code + 自架後端（confidential client）**：client secret 只放後端，callback 與 token 交換在後端完成，符合原文「後端用來部署 OAuth callback 與 token 交換邏輯」的預期。需考慮 token 如何從後端安全交回本機 plugin（例如一次性 session code、本機輪詢、PKCE 綁定）。
- **Authorization Code + PKCE**：防止授權碼被攔截。可與後端方案併用。
- **Loopback redirect（127.0.0.1）desktop flow**：不需後端，但 Google 的 desktop client 仍有 client secret（非機密），且與原文預期的「自架後端」較不吻合。
- **Device flow**：Google 的 device flow 不支援 Drive 完整讀取 scope，不適用。
- 需防範：`state` 參數防 CSRF、redirect URI 精確比對、不在 URL／log 中洩漏 token。

## Token 保存

- Refresh token 長期有效，是主要保護對象；access token 約 1 小時過期，需自動 refresh。
- 可選方案：
  - 本機：OS keychain（macOS Keychain／Windows Credential Manager／Linux Secret Service），或權限 `0600` 的使用者設定檔。
  - 後端：加密儲存，本機只持有不透明的 session 識別碼。
- 不可：寫死在程式碼、commit 進 repo、印到 log。
- `.gitignore` 排除所有 credential／token 檔案；提供 `.env.example`。
- 提供「登出／清除 token」的方式（加分）。

## Google Drive API 讀取細節

- **列出資料夾**：`files.list` 以 `'<folderId>' in parents and trashed = false` 查詢；需處理 `nextPageToken` 分頁。
- **子資料夾**：mimeType 為 `application/vnd.google-apps.folder`，需遞迴（注意深度上限與循環防護）。
- **被分享的資料夾／共用雲端硬碟**：加上 `supportsAllDrives=true`、`includeItemsFromAllDrives=true`，避免在 shared drive 情境下查不到。
- **捷徑（shortcut）**：mimeType `application/vnd.google-apps.shortcut`，需透過 `shortcutDetails.targetId` 解析。
- **讀取內容**：
  - 一般檔案（PDF、圖片等）：`files.get?alt=media` 下載。
  - Google 原生格式（Docs／Sheets／Slides）：需用 `files.export` 轉成 text／csv 等，不能直接 `alt=media`。
- **PDF**：嘗試抽取文字；掃描型 PDF 可能沒有文字層 → 回報無法抽取，或交由 Claude 以文件／圖片方式理解。
- **圖片**：無法直接抽文字 → 可將圖片內容以 MCP image content 回傳給 Claude 多模態理解，或回傳中繼資料並說明。
- **大小限制**：設定讀取上限，避免超大檔案塞爆 context。
- **資料夾 ID**：建議同時接受完整 URL 與純 ID，並在 plugin 設定中預設測試資料夾。

## Claude Code Plugin 形態

- 預期結構：plugin manifest + MCP server（提供如 `list_files`、`read_file`、`authorize`／`auth_status` 等工具）。
- 工具名稱與描述要讓 Claude 在自然語言「列出檔案」「讀出內容」時能正確選用。
- 安裝方式需能「從 repo 直接安裝」（例如透過 plugin marketplace 加入 GitHub repo）；實作時以 Claude Code 官方 plugin 文件為準。
- MCP server 的執行依賴（Node／Python 版本等）需在 README 列明，或盡量打包成免額外安裝。

## 安全性

- client secret 只存在後端環境變數，不進 repo、不進 plugin。
- 後端只做 OAuth callback 與 token 交換（以及 refresh），不代理或保存檔案內容。
- 後端交回 token 的通道需防止被他人冒領（一次性、短效、綁定發起端）。
- 全程 HTTPS。

## 時程風險

- 期限兩週，且交付後驗收時間未知 → 後端、OAuth Client、token 機制需在交付後持續可用。
