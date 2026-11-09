# 實作規格：Drive Reader Plugin

> 來源：原作業說明（[docs/spec/](spec/)）、出題方來信要求（[spec 01](spec/01-overview.md#出題方來信的額外要求)）、2026-11-09 設計討論。
> 名詞以 [CONTEXT.md](../CONTEXT.md) 為準；授權鏈路的核心決策見 [ADR 0001](adr/0001-refresh-token-held-locally-stateless-broker.md)。

## Problem Statement

OakMega 審閱者要在**自己的環境**、用**自己的 Google 帳號**，在 Claude Code 裡用自然語言讀出一個別人分享給他們的 Drive 資料夾內容（PDF、圖片、子資料夾）。他們只看 README，不會看程式碼才安裝，開發者也不在場。

評分重點是 OAuth 流程是否順暢、安全，讀取路徑是否穩定，以及（來信要求）開發者能否說明每一行邏輯的作用與技術取捨。

## Desired Outcome

- 依 README 兩行指令安裝 plugin 後不需要任何設定，就能用自然語言完成一次完整授權。
- 「列出資料夾內的檔案」會回傳 Root Folder 的完整子樹。
- 「讀出檔案的內容」時：
  - 有文字層的 PDF 回傳文字；掃描型 PDF 與圖片交給 Claude 視覺理解。
  - 其他類型得到清楚的 Read Limitation 說明，不會崩潰或卡住。
- 任何 Failure 都會告訴使用者**發生了什麼**以及**下一步怎麼做**。
- 程式碼量小、依賴少，非顯而易見的取捨都記錄在註解或 ADR 中。

## Ubiquitous Language

完整定義見 [CONTEXT.md](../CONTEXT.md)，以下是本規格依賴的名詞：

- **Root Folder**：存取邊界。
- **Token Broker**：持有 client secret 的無狀態後端。
- **Code Relay**：callback 將 auth code 轉交到本機 loopback 的步驟。
- **Authorization Attempt**：一次進行中的授權嘗試，短效、一次性。
- **Local Credential**：本機保存的 refresh token。
- **Read Limitation**：內容無法完整交付的情況，屬於正常結果。
- **Failure**：存取路徑走不通、使用者需要採取行動的情況。

## Bounded Contexts and Ownership

共三個 context，分屬兩個部署單元：`backend/`（你部署的）與 `plugin/`（使用者安裝的）。MCP tool 層與 plugin 打包屬於 adapter，不另立 context。

### 1. Token Broker（部署單元：Cloud Run 上的 FastAPI，目錄 `backend/`）

- **職責**：保管 OAuth Client 設定（client_id、client secret、redirect_uri、scope），代表本機完成與 Google token endpoint 之間需要 secret 的互動。
- **擁有的狀態**：無。只有部署時注入的設定。
- **擁有的不變式**：見 Domain Rules B1–B5。
- **不負責**：
  - 保存任何使用者 token 或 code
  - 驗證 `state` 的隨機部分
  - 呼叫 Drive API
  - revoke（本機直接呼叫 Google，因為 revoke 不需要 secret）

### 2. Local Authorization（部署單元：本機 MCP server）

- **職責**：Authorization Attempt 的生命週期、Local Credential 的保存與刪除、提供有效的 access token。
- **擁有的狀態**：
  - Authorization Attempt（記憶體）
  - Local Credential（檔案）
  - access token 快取（記憶體）
- **擁有的不變式**：見 Domain Rules A1–A6。
- **不負責**：持有 client secret、組 Google 授權 URL（屬於 Broker）、任何 Drive 讀取邏輯。

### 3. Drive Reading（部署單元：本機 MCP server）

- **職責**：
  - Root Folder 邊界
  - 列出子樹
  - 依檔案類型取得並轉換內容
  - 區分 Read Limitation 與 Failure
- **擁有的狀態**：無持久狀態。Root Folder 由設定提供。
- **擁有的不變式**：見 Domain Rules R1–R7。
- **不負責**：token 的取得與刷新（透過 C2 向 Local Authorization 取得）、授權流程。

### Adapter：MCP Tool Surface 與 Plugin 打包

- 把 tool 呼叫對應到上述 use case，將 Failure 格式化成 `[代碼] 原因。下一步：…`。
- 包含 `.claude-plugin/`、`.mcp.json`、`uv` 啟動設定。
- 沒有業務規則。

## Affected Surfaces

| Surface | 內容 |
|---|---|
| **Backend** | Token Broker（FastAPI，Cloud Run，自訂網域） |
| **Local plugin**（外部整合，非 Mobile/Web） | Python MCP server（stdio）、Claude Code plugin／marketplace manifest |
| **External integration** | Google OAuth 2.0（authorize、token、revoke）、Google Drive API v3、Cloud Run、Secret Manager、Cloudflare DNS |
| **Docs** | README（使用者路徑與重建路徑）、`docs/architecture.md`、ADR |

不涉及 Mobile 或 Web UI。Broker 的 `/`、`/privacy`、授權結果頁只是靜態 HTML，不構成 Web surface。

## Domain Rules and Invariants

### Token Broker

- **B1** Broker 不持久化、也不記錄任何 auth code、access token、refresh token。log 只記方法、路徑、狀態碼。
- **B2** Code Relay 的目標只能是 `http://127.0.0.1:<port>/callback`：
  - `port` 從 `state` 的 `<port>.<nonce>` 格式解析，必須是 1024–65535 的整數
  - 格式不合時回 400 錯誤頁，不轉址
- **B3** `/token` 只接受兩種請求：
  - `authorization_code`（附 `code`、`code_verifier`）
  - `refresh_token`（附 `refresh_token`）

  其他一律 422。
- **B4** 授權請求的 scope 固定為 `https://www.googleapis.com/auth/drive.readonly`，不接受本機指定。
- **B5** `redirect_uri` 永遠等於 Broker 自己的 `${PUBLIC_BASE_URL}/callback`，`/authorize` 與 `/token` 使用同一個值。

### Local Authorization

- **A1** 同一個 MCP server process 中，同時最多一個 Authorization Attempt。新的 `authorize` 會關閉並取代舊的。
- **A2** Authorization Attempt 是一次性的，5 分鐘後過期：
  - listener 收到第一個 callback 後就關閉，不論成功或失敗
  - `state` 的 nonce 以常數時間比對
- **A3** Local Credential 只保存 refresh token（與 scope、取得時間）。access token 只放在記憶體。
- **A4** Local Credential 檔案不會以寬於 `0600` 的權限存在：
  - 目錄權限為 `0700`
  - 檔案以 `O_CREAT` 加 `0o600` 建立，先寫入暫存檔再用 `os.replace` 原子替換
  - **Windows 例外**：Windows 會忽略 POSIX 權限位元，`os.open` 的 mode 無效。保護來自檔案位於使用者設定檔目錄下，預設 ACL 只允許該使用者存取。程式不另外設定 ACL，此差異在 README 與架構說明中寫明，不宣稱 Windows 上有 `0600`。
- **A5** refresh 時收到 `invalid_grant`，表示 Local Credential 已失效，應立即刪除。
- **A6** `logout` 先向 Google revoke，再刪除檔案。revoke 失敗不阻擋刪除，但要回報給使用者。

### Drive Reading

- **R1** `list_files` 與 `read_file` 的目標都必須位於 Root Folder 子樹內：
  - 沿 `parents` 往上追溯，遇到 Root Folder 才放行
  - 追溯最多 20 層；超過層數，或碰到無法存取的祖先，都視為超出範圍
- **R2** 捷徑的處理：
  - 列出時不跟進，只標示目標 ID
  - 讀取時解析目標，並對**目標**套用 R1
- **R3** 列出時，遞迴深度最多 5 層，總項目數最多 500 筆，用 visited set 防止循環，並處理所有分頁。超過上限時截斷並註明。
- **R4** 交付給 Claude 的內容都有上限：
  - 下載 ≤ 20MB（下載前用 `size` 判斷）
  - 文字 ≤ 50,000 字
  - PDF 算繪 ≤ 5 頁（整份文件合計）
  - 圖片長邊 ≤ 1568px
- **R4a** PDF **逐頁**判斷：抽出的文字量低於門檻的頁面，就算繪成影像。回傳時依頁碼順序穿插文字與影像，因此混合文字頁與掃描頁的 PDF 不會漏讀。超過 R4 上限的頁面不回傳，並註明「第 N 頁以後省略」。
- **R5** 不支援的類型、過大、截斷、無文字層改用影像，都屬於 **Read Limitation**，以正常結果回傳，並附上中繼資料與原因。
- **R6** **Failure** 一定帶有代碼與「下一步」。Drive 回 404 時一律視為「找不到或沒有權限」，並附上目前授權帳號的 email。
- **R7** 只對安全且可重試的 Google 呼叫自動重試（GET、export、about），遇到 429 或 5xx 時以指數退避重試 2 次。

### 驗證與呈現（不屬於 domain 不變式）

- 資料夾與檔案參數都接受純 ID 或 Drive URL，解析後統一成 ID。
- tool 描述以中英雙語列出常見說法；回傳給使用者的訊息用繁中。

## Context Map and Dependency Direction

```
Google OAuth ──▶ Token Broker ──C1──▶ Local Authorization ──C2──▶ Drive Reading ──▶ MCP Tool Surface ──C3──▶ Claude
                                       │                            ▲
                                       └── Google revoke            └── Google Drive API v3（C4）
```

- **Token Broker → Local Authorization（C1）**：只有 Broker 持有 secret，換 token 與 refresh 都必須經過它。
- **Local Authorization → Drive Reading（C2）**：Drive Reading 只需要「一個有效的 access token」，不應知道 token 從哪裡來。
- **Drive Reading → MCP Tool Surface（C3）**：tool 層只做轉接與格式化。
- 圖中沒有循環。Drive Reading 收到 401 時，會透過 C2 的 `invalidate()` 通知 Local Authorization；這是同一份合約的一部分，不是反向依賴。

## Public Contracts

所有合約都是**新建**的，沒有既有的消費者。下面標示的 impact 是指未來修改時，哪些變更算破壞性。

### C1 Token Broker HTTP API

提供者：Token Broker。消費者：Local Authorization、使用者的瀏覽器。

| Endpoint | 輸入 | 成功 | 失敗 |
|---|---|---|---|
| `GET /authorize` | `state=<port>.<nonce>`、`code_challenge`（S256） | 302 到 Google，參數為 `client_id`、`redirect_uri`、`response_type=code`、`scope`（B4）、`access_type=offline`、`prompt=consent`、`code_challenge_method=S256`，`state` 原樣帶上 | 400 HTML（`state` 或 challenge 格式不合） |
| `GET /callback` | Google 回傳的 `code`、`state` 或 `error`、`state` | 302 到 `http://127.0.0.1:<port>/callback`，參數原樣轉交（B2） | 400 HTML（`state` 格式不合） |
| `POST /token` | JSON：`{grant_type:"authorization_code", code, code_verifier}` 或 `{grant_type:"refresh_token", refresh_token}` | 200：`{access_token, expires_in, scope, token_type, refresh_token?}` | 422（形狀不合）；400 `{error, error_description}`（原樣轉交 Google 的錯誤，例如 `invalid_grant`）；502 `{error:"upstream_unavailable"}` |
| `GET /`、`GET /privacy` | — | 靜態頁（同意畫面需要的首頁與隱私權政策） | — |
| `GET /healthz` | — | 200 `ok` | — |

- `prompt=consent` 確保每次授權都會拿到 refresh token。Google 預設只在第一次同意時才會給。
- 破壞性變更：`state` 格式、`/token` 的請求或回應形狀、錯誤代碼的語意。新增選填欄位屬於相容變更。

### C2 Access Token Provider（MCP server 內部）

提供者：Local Authorization。消費者：Drive Reading。

- `get_access_token() -> str`：
  - 回傳有效 token；距離過期不到 60 秒就先 refresh
  - 可能拋出 `NotAuthorized`、`AuthExpired`、`BrokerUnreachable`
- `invalidate() -> None`：Drive 回 401 時呼叫。下一次 `get_access_token` 會強制 refresh，每次請求最多重來一次。
- `current_account() -> str | None`：已授權帳號的 email，來自 Drive `about.get(fields=user)`，供 R6 使用。
- 破壞性變更：例外種類或語意改變。

### C3 MCP Tools

提供者：MCP Tool Surface。消費者：Claude（模型）。

| Tool | 參數 | 回傳 |
|---|---|---|
| `list_files` | `folder?`（ID 或 URL，預設 Root Folder）、`recursive=True` | 每行一個項目：相對路徑、mimeType、大小、修改時間、ID；捷徑另外標示目標 ID；截斷時附註 |
| `read_file` | `file`（ID 或 URL） | 文字 content；或 image content 加一行中繼資料；或 Read Limitation 說明。若參數是資料夾，回 Failure 並提示使用 `list_files` |
| `authorize` | — | 立即回傳授權 URL 與「完成後告訴我」；背景等待 Code Relay |
| `auth_status` | — | 是否已授權、帳號 email、是否有進行中的 Authorization Attempt |
| `logout` | — | revoke 與刪除的結果 |

Failure 代碼如下，代碼與語意都屬於合約：

| 代碼 | 意義 |
|---|---|
| `NOT_AUTHORIZED` | 尚未授權 |
| `AUTH_EXPIRED` | 授權已失效 |
| `NOT_FOUND_OR_NO_ACCESS` | 找不到或沒有權限 |
| `OUTSIDE_ROOT` | 目標不在 Root Folder 子樹內 |
| `NOT_A_FILE` | 傳入的是資料夾 |
| `BROKER_UNREACHABLE` | 連不到 Broker |
| `GOOGLE_API_ERROR` | Google API 錯誤 |

破壞性變更：tool 名稱、必填參數、Failure 代碼語意。

### C4 外部提供者：Google APIs（只消費，不擁有）

用到的 API：
- Drive v3：`files.list`（`supportsAllDrives`、`includeItemsFromAllDrives`）、`files.get`（`fields`、`alt=media`）、`files.export`、`about.get`
- OAuth：`/token`（只由 Broker 呼叫）、`/revoke`（只由本機呼叫）

各類型的 export 格式：

| 類型 | 匯出成 | 備註 |
|---|---|---|
| Google 文件 | `text/markdown` | |
| Google 試算表 | `text/csv` | 只有第一個工作表，回傳時會註明 |
| Google 簡報 | `text/plain` | |

### C5 設定合約

| 位置 | 變數 | 預設 |
|---|---|---|
| 本機 | `DRIVE_READER_BROKER_URL` | 正式 Broker 網址 |
| 本機 | `DRIVE_READER_ROOT_FOLDER` | 測試資料夾 `1AU6ZW-3NFxme6388YPe98bGWWh9q_E5Y`（也接受 URL） |
| 本機 | `DRIVE_READER_CREDENTIALS_PATH` | `~/.config/claude-drive-reader/credentials.json` |
| Broker | `GOOGLE_CLIENT_ID`、`PUBLIC_BASE_URL` | 無，必填 |
| Broker | `GOOGLE_CLIENT_SECRET` | 無，必填，來自 Secret Manager |

## Consistency and Transactions

- 沒有共享資料庫，也沒有跨 context 的交易。唯一的持久狀態是 Local Credential 檔案，以原子替換保證不會寫到一半（A4）。
- 多個 Claude Code 視窗代表多個 MCP process：
  - 各自 refresh，Google 允許同一個 refresh token 發出多個 access token
  - 同時授權時，最後寫入的 Local Credential 生效，可以接受
- 冪等性：
  - auth code 只能用一次，因此 `authorization_code` 換 token **不重試**
  - `refresh_token` 與 Drive 的讀取呼叫可以安全重試（R7）
- 如果 Google 在 refresh 回應中附了新的 refresh token，就覆寫 Local Credential，否則不寫入。

## User Scenarios

1. **首次使用**：使用者說「列出資料夾內的檔案」→ `NOT_AUTHORIZED` → Claude 呼叫 `authorize` → 顯示 URL 並嘗試開啟瀏覽器 → 使用者看到未驗證警告，點「進階」繼續並同意 → 本機頁面顯示「授權完成」→ 使用者說「好了」→ 列出完整子樹。
2. **瀏覽器無法自動開啟**（SSH、WSL）：同情境 1，但由使用者手動點擊 Claude 顯示的 URL，結果相同。
3. **使用者拒絕授權**：本機頁面與 `auth_status` 都顯示「已拒絕」，Local Credential 不變。
4. **授權逾時**：5 分鐘內沒有完成，listener 自動關閉；`auth_status` 顯示沒有進行中的授權，重新 `authorize` 即可。
5. **讀取有文字層的 PDF**：回傳文字，超過 50k 字時截斷並註明。
6. **讀取掃描型 PDF**：回傳前 5 頁影像，並註明「無文字層」。
6a. **讀取混合型 PDF**（部分頁面有文字、部分是掃描頁）：依頁碼順序回傳，有文字的頁面給文字，掃描頁給影像。
7. **讀取圖片**：縮放後以 image content 回傳，Claude 描述內容。若格式無法處理，回報 Read Limitation 與中繼資料。
8. **讀取子資料夾內的檔案**：使用列出時取得的 ID，通過 R1 檢查後讀取。
9. **讀取 Google 文件、試算表、簡報**：匯出後回傳，試算表會註明只有第一個工作表。
10. **讀取不支援的類型或過大的檔案**：回報 Read Limitation 與中繼資料，不下載。
11. **用錯帳號授權，或還沒接受分享邀請**：`NOT_FOUND_OR_NO_ACCESS`，附上目前帳號 email 與「請接受邀請，或先 `logout` 換帳號」。
12. **授權已被撤銷**（使用者在 Google 帳號頁撤銷）：refresh 拿到 `invalid_grant`，刪除 Local Credential，回傳 `AUTH_EXPIRED`，要求重新 `authorize`。
13. **prompt injection**：檔案內容誘導 Claude 讀取 Root Folder 外的檔案，`read_file` 回傳 `OUTSIDE_ROOT`。
14. **Broker 無法連線**：回傳 `BROKER_UNREACHABLE`，附上 Broker 網址。
15. **登出**：revoke 並刪除檔案，之後任何讀取都回到 `NOT_AUTHORIZED`。
16. **使用超過一小時**：access token 過期，自動透過 Broker refresh，使用者不會察覺。

## Implementation Decisions

- **授權流程與 token 存放**：見 ADR 0001。Broker 無狀態，refresh token 存在本機，以 PKCE 綁定發起端，`state` 夾帶 port 以完成 Code Relay。
- **Broker 技術**：FastAPI。只用 route 與 pydantic，不使用 DI，關閉 `/docs` 與 `/openapi.json`。對外呼叫用 `httpx`。部署在 Cloud Run，與 OAuth Client 同一個 GCP 專案；secret 放在 Secret Manager；使用自訂網域。
- **同意畫面**：Production、不送驗證（restricted scope 的驗證需要 CASA，不在範圍內）。README 附警告畫面的說明。
- **MCP server 技術**：Python 官方 `mcp` SDK（stdio），透過 `uv run --directory ${CLAUDE_PLUGIN_ROOT}/mcp-server` 啟動，依賴版本由 `uv.lock` 鎖定。
- **檔案類型處理**：
  - PDF 用 `pypdfium2` 逐頁處理：有文字的頁面回傳文字，沒有文字的頁面算繪成影像（R4a）
  - 圖片用 Pillow 縮放或轉檔
  - SVG 與文字類型以 UTF-8 文字回傳
  - 不解析 docx、xlsx 等格式
- **授權觸發**：非阻塞的 `authorize`，listener 在背景執行（A1、A2）。
- **安全邊界**：
  - scope 只有 `drive.readonly`
  - Root Folder 作為存取邊界，防範 prompt injection
  - 帳號 email 用 `about.get` 取得，不額外要求 `email` scope
- **錯誤模型**：分成 Read Limitation 與 Failure（R5、R6）。Drive 的 404 一律視為無權限的可能。
- **程式碼風格**（C-2）：
  - 識別字與 commit 用英文
  - 註解用繁中，只寫「為什麼」
  - 不引入只為了「可能會用到」的抽象層
- **Repo 形態**：頂層目錄依部署面命名，程式套件依領域命名：
  - `backend/`：你部署的 Token Broker，套件名稱 `token_broker`。
  - `plugin/`：使用者安裝的部分，包含 `.claude-plugin/plugin.json`、`.mcp.json`、`mcp-server/`（套件名稱 `drive_reader`）。
  - repo 根目錄的 `.claude-plugin/marketplace.json` 以 `source: "./plugin"` 指向 plugin，因此驗收者只會安裝 `plugin/`，不會拿到後端程式碼。
  - 交付時 repo 改成 public。

## Recommended Implementation Order

0. **外部前置作業**（使用者負責）：
   - GCP 專案、billing、啟用 API
   - 同意畫面、OAuth Client
   - Secret Manager、子網域、Search Console 驗證
   - 接受測試資料夾的分享邀請，準備第二個帳號

   → 完成後，C1 的外部依賴才存在。
1. **Token Broker（C1）**：先以測試鎖定 B1–B5，再部署到 Cloud Run 並綁定網域，最後用瀏覽器手動走一次 `/authorize` 到 Google 的流程。

   → **C1 穩定**，解鎖 Local Authorization。也最早確認同意畫面、網域、未驗證警告的實際行為。
2. **Plugin 骨架加 Local Authorization（C2，以及 C3 的授權相關 tool）**：
   - marketplace、plugin、`.mcp.json` 與 `uv` 啟動
   - Authorization Attempt、Local Credential、`authorize`、`auth_status`、`logout`
   - **spike**：確認 Claude Code 會把 MCP 的 image content 交給模型

   → 用第二個帳號完成一次真實授權。**C2 穩定**，解鎖 Drive Reading。
3. **Drive Reading：存取與列出**：Drive client adapter、ID 或 URL 解析、R1 邊界檢查、`list_files`（R2、R3），以及 404 與 401 的錯誤對應。

   → 讀取路徑的存取層穩定。
4. **Drive Reading：內容處理**：依序完成 Google 原生格式 export、文字、PDF、圖片、不支援的類型（R4、R5），最後是 R7 重試。

   → FR-3 到 FR-5 完成。
5. **文件與 Release 驗收**：README 的兩條路徑、`docs/architecture.md`、截圖；在乾淨環境照 README 走一遍；掃描 git 歷史確認沒有 secret；repo 改成 public。

**可以平行的部分**：C1 的形狀（本文件）與 C2 的介面定案後，步驟 3、4 就能用假的 Access Token Provider 與假的 Drive 進行，不必等步驟 1、2 部署完成。但真實的端到端驗證必須等 1、2 完成。

## Verification Strategy

> Previously verified dependencies are trusted unless they or their public contracts change.

| 變更區域 | 驗證範圍 | 必要測試 | 不需要跑 |
|---|---|---|---|
| Token Broker 內部 | Context | pytest 加 `httpx.MockTransport`：B2 各種惡意 `state`（非數字、超出範圍、夾帶 host 或路徑）、B3 的 422、B1（log 不含 token）、`/authorize` 組出的 URL 參數 | MCP server 測試 |
| C1 形狀變更 | Contract | Broker 測試，加上 Local Authorization 的 Broker client 測試 | Drive Reading 測試 |
| Local Authorization | Context | Authorization Attempt 生命週期（一次性、逾時、取代、`state` 不符、使用者拒絕）、A4 權限與原子寫入、A5 `invalid_grant` 時刪除、A6 logout、C2 的 refresh 時機與 `invalidate` | Broker 測試、Drive Reading 內容處理 |
| Drive Reading：存取與列出 | Context | 假 Drive：R1（含共用雲端硬碟、無法存取的祖先）、R2 捷徑、R3 上限、循環、分頁、404 與 401 的對應 | Broker 測試、Local Authorization 測試 |
| Drive Reading：內容處理 | Local | fixture：有文字的 PDF、純影像的 PDF、**混合型 PDF**、PNG、超大圖片、不支援的類型；R4、R4a 上限與頁序、R5 回傳形狀 | 其他所有測試 |
| MCP Tool Surface（C3） | Contract | tool 註冊與參數 schema、Failure 格式 `[代碼] … 下一步：…` | 內部 handler 細節（已由 context 測試涵蓋） |
| 共用或 plugin 打包（`.mcp.json`、`uv.lock`） | System | 在乾淨環境執行 `uv run` 啟動，並以 MCP 握手驗證 | — |
| 交付里程碑 | Release | 在乾淨的 Claude Code 環境照 README 安裝，用第二個帳號跑完 spec 09 的自我驗收清單（情境 1–16，其中情境 16 要等 access token 實際過期後再讀一次），結果記錄在 `docs/` | — |

- CI（GitHub Actions）在 push 時，於 **ubuntu、macos、windows 三個平台**執行全部 pytest，不連真實的 Google。credential 權限測試在 Windows 上改為驗證「不宣稱 `0600`」的行為。
- 手動 Release 驗收至少在開發機以外的一個作業系統上進行一次。若手邊沒有其他作業系統，就以 CI 的三平台結果為準，並在驗收紀錄中註明。
- 真實的 Google 流程只在步驟 1、2 完成時，以及 Release 驗收時手動執行。

## Migration / Compatibility

不適用。這是全新系統，沒有既有資料或消費者。

唯一的「相容性」考量是：交付後如果修改 C1，已安裝的驗收者 plugin 可能和新的 Broker 不相容。因此**交付後 C1 視為凍結**，只允許相容變更。

## Out of Scope

- 搜尋、寫入、監聽變更（原作業明列為非目標）
- docx、xlsx 等 Office 格式解析；OCR
- OS keychain 儲存（在架構說明中列為正式產品的 trade-off）
- 多個 Root Folder；在執行期間透過 tool 切換 Root Folder
- restricted scope 的 Google 驗證（CASA）
- CI 對真實 Drive 的整合測試
- Broker 的速率限制或濫用防護（列為已知限制）

## Assumptions and Open Risks

| # | 假設或風險 | 影響 | 驗證時機與後備方案 |
|---|---|---|---|
| 1 | Claude Code 會把 MCP 的 image content 交給模型 | 掃描型 PDF 與圖片的處理策略 | 步驟 2 的 spike。不成立時退回只回傳中繼資料的 Read Limitation |
| 2 | 未驗證的 Production app 使用 `drive.readonly` 時，會出現「可繼續」的警告，而不是直接封鎖 | 整條 OAuth 路線（最高風險） | 步驟 1 一部署就實測。若被封鎖，要重新討論（例如改成 Testing 加 test users） |
| 3 | 選定的 region 支援 Cloud Run domain mapping | Broker 網域與 Authorized domains | 步驟 1。不支援時用 `*.run.app`，或在 Cloudflare 前面加一層代理 |
| 4 | 第一次 `uv run` 下載 Python 與依賴時，不會超過 Claude Code 的 MCP 啟動逾時 | 驗收者的第一印象 | 步驟 2 在乾淨環境實測。README 加上預熱步驟 |
| 5 | `/token` 是公開端點，任何拿到 refresh token 的人都能透過它 refresh | 安全性 | 接受的風險（ADR 0001），寫入架構說明 |
| 6 | Drive 支援把 Google 文件 export 成 `text/markdown` | 原生格式的讀取 | 步驟 4。不支援時改用 `text/plain` |
| 7 | 驗收在 2026-11-23 之後的某個時間進行 | Broker、OAuth Client、Production 狀態都必須持續有效 | 交付後不修改 C1，Cloud Run 免費額度足夠 |
| 8 | 從 GitHub 安裝時，marketplace 的 plugin `source` 可以指向子目錄 `./plugin` | 安裝路徑 | 步驟 2 第一個驗證。不支援時退回 `"./"`，plugin 檔案移回 repo 根目錄 |
| 9 | 驗收者使用的作業系統和開發機不同（Windows、macOS） | 安裝與執行的穩定性 | CI 三平台矩陣；Windows 權限差異見 A4；`uv`、`pypdfium2`、Pillow 都有三平台的預編譯版本 |
