# Drive Reader

[![CI](https://github.com/isaiah-oakmega/claude-drive-reader/actions/workflows/ci.yml/badge.svg)](https://github.com/isaiah-oakmega/claude-drive-reader/actions/workflows/ci.yml)

讓 Claude Code 用自然語言讀取一個指定的 Google Drive 資料夾：列出檔案（含子資料夾），讀取 PDF、圖片、文字檔與 Google 文件、試算表、簡報的內容。只要求唯讀權限（`drive.readonly`），而且只讀得到設定的資料夾範圍內的檔案。

- 想直接使用：看[快速開始](#快速開始)，大約 5 分鐘。
- 想用自己的 Google Cloud 專案與後端重建一套：看[自行重建](#自行重建)。
- 想了解設計：看[架構說明](docs/architecture.md)。

---

## 快速開始

### 需要準備

| 項目 | 說明 |
|---|---|
| Claude Code（終端機版）v2.1.292 以上 | 用 `claude --version` 確認。安裝方式見 [Claude Code 文件](https://code.claude.com/docs/en/setup) |
| [uv](https://docs.astral.sh/uv/) | 安裝 plugin 時，用它下載 Python 3.12 與相依套件；不需要事先安裝 Python |
| 一個 Google 帳號 | 能存取要讀取的 Drive 資料夾（如果是別人分享的，請先接受分享邀請） |
| 在**本機**執行 Claude Code | 授權時，瀏覽器和 Claude Code 必須在同一台電腦上。SSH 遠端的用法見[疑難排解](#疑難排解) |

### 1. 安裝 uv

macOS、Linux：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Windows（PowerShell）：

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

裝完後**重開終端機**，執行 `uv --version` 確認。

> Windows 提醒：先裝 uv、再裝 Claude Code。uv 的安裝程式會把 `%USERPROFILE%\.local\bin` 加進 PATH，Claude Code 也裝在同一個資料夾。如果 `claude` 顯示 `is not recognized`，見[疑難排解](#疑難排解)。

### 2. 安裝 plugin

在終端機執行（不需要先開啟 Claude Code）：

```bash
claude plugin install drive-reader --marketplace isaiah-oakmega/claude-drive-reader
```

看到 `Successfully installed plugin: drive-reader@drive-reader-marketplace` 就完成了。

也可以在 Claude Code 裡面安裝，結果相同：

```
/plugin marketplace add isaiah-oakmega/claude-drive-reader
/plugin install drive-reader@drive-reader-marketplace
```

接著在終端機**先把 plugin 的執行環境裝好**。這一步會下載 Python 3.12 與相依套件，實測約 10 到 30 秒，視網路速度而定。Claude Code 啟動 plugin 時最多只等 30 秒，第一次安裝如果留給 Claude Code 做，網路較慢時會逾時，所以先在這裡做完。第一次安裝、以及每次更新 plugin 之後都要做一次。

Windows（PowerShell）：

```powershell
$p = (Get-Content "$HOME\.claude\plugins\installed_plugins.json" -Raw | ConvertFrom-Json).plugins.'drive-reader@drive-reader-marketplace'[0].installPath
uv sync --frozen --no-dev --directory $p
```

macOS、Linux：

```bash
p=$(grep -o '"installPath": *"[^"]*/drive-reader-marketplace/drive-reader/[^"]*"' ~/.claude/plugins/installed_plugins.json | head -1 | cut -d'"' -f4)
uv sync --frozen --no-dev --directory "$p"
```

最後一行顯示 `Installed … packages`（已經裝過的話是 `Checked` 或 `Audited`）就完成了。

然後**重新啟動 Claude Code**，輸入 `/mcp`，確認 `plugin:drive-reader:drive` 顯示 connected。如果顯示 `connection timed out after 30000ms`，見[啟動逾時](#啟動逾時)。

> 使用 Claude Desktop 的 Code 分頁：Desktop 不能從畫面上加入 GitHub 上的 marketplace，請先在終端機執行上面的安裝指令。同一台電腦上的 Desktop 和終端機版共用設定，裝好後在 Desktop 開新的 session 就能使用。

### 3. 授權

在 Claude Code 說「**列出資料夾內的檔案**」。第一次使用時 Claude 會發現還沒授權，接著幫你開始授權：

1. Claude 顯示一個授權網址，並嘗試自動開啟瀏覽器。沒有自動開啟的話，手動點網址。
2. 選擇要使用的 Google 帳號。
3. Google 會顯示「**Google 尚未驗證這個應用程式**」的警告，畫面上的名稱是網域 `isaiahlin.dev`。點「**進階**」，再點「**前往 isaiahlin.dev（不安全）**」。
4. 確認要求的權限只有「查看及下載」雲端硬碟檔案（唯讀，不能修改或刪除），按「**繼續**」。
5. 瀏覽器顯示「**授權完成**」後，回到 Claude Code 說「好了」。

為什麼會有警告：Drive 的唯讀權限屬於 Google 的 restricted scope，要移除警告必須通過付費的第三方安全評估（CASA），超出這份作業的範圍。授權網址在 5 分鐘內有效；逾時或想換帳號，再說一次「幫我授權」即可。

### 4. 使用

直接用自然語言描述需求，Claude 會選擇對應的 tool：

| 你可以說 | 會發生什麼 |
|---|---|
| 「這個資料夾有什麼？」「列出資料夾內的檔案」 | 列出整個資料夾，包含子資料夾（最多 5 層、500 筆） |
| 「報告那個子資料夾裡有哪些檔案？」 | 只列出該子資料夾 |
| 「幫我看會議記錄那份 PDF 寫了什麼」 | 讀取 PDF：有文字的頁面回傳文字，掃描頁回傳頁面影像 |
| 「這張圖片是什麼？」 | 以圖片交給 Claude 描述（長邊縮到 1568px） |
| 「摘要一下預算試算表」 | Google 文件、試算表、簡報匯出成文字後讀取 |
| 「授權狀態如何？」「我現在是哪個帳號？」 | 顯示是否已授權、帳號 email、上一次授權的結果 |
| 「登出」 | 撤銷授權並刪除本機保存的授權 |

讀不了的檔案（不支援的類型、超過 20MB、有密碼的 PDF……）會回報原因與檔案資訊，不會讓對話中斷。

### 設定

預設讀取的資料夾是這份作業指定的測試資料夾。所有設定都是選填的環境變數：

| 變數 | 預設 | 說明 |
|---|---|---|
| `DRIVE_READER_ROOT_FOLDER` | 作業的測試資料夾 | 要讀取的資料夾，可以填 ID 或 Drive 網址。只有這個資料夾範圍內的檔案讀得到 |
| `DRIVE_READER_BROKER_URL` | `https://drive-auth.isaiahlin.dev` | 換 token 的後端。[自行重建](#自行重建)時改成你的網址。必須是 https（只有 localhost 可以用 http） |
| `DRIVE_READER_CREDENTIALS_PATH` | `~/.config/claude-drive-reader/credentials.json` | 授權保存的位置 |
| `DRIVE_READER_CALLBACK_PORT` | 不設定（由作業系統挑選） | 授權時本機等待結果的 port，只有 SSH 轉送時才需要固定 |

設定方式（擇一）：

- 寫在 Claude Code 的 `~/.claude/settings.json`，所有 session 都會套用：
  ```json
  { "env": { "DRIVE_READER_ROOT_FOLDER": "https://drive.google.com/drive/folders/<資料夾 ID>" } }
  ```
- 或設成系統的環境變數，再重新啟動 Claude Code。Windows（PowerShell）：
  ```powershell
  [Environment]::SetEnvironmentVariable('DRIVE_READER_ROOT_FOLDER', '<資料夾 ID>', 'User')
  ```

設定錯誤時（例如 port 不是 1024–65535 的整數），plugin 會啟動失敗，`/mcp` 顯示 failed，錯誤原因寫在 Claude Code 的 MCP log 中。

### 錯誤訊息

出錯時 Claude 會收到 `[代碼] 原因。下一步：…` 格式的訊息，並轉告你下一步怎麼做：

| 代碼 | 意思 | 怎麼處理 |
|---|---|---|
| `NOT_AUTHORIZED` | 還沒授權 | 照[授權](#3-授權)步驟完成 |
| `AUTH_EXPIRED` | 授權已失效（例如在 Google 帳號頁撤銷了存取權） | 重新授權 |
| `NOT_FOUND_OR_NO_ACCESS` | 找不到，或目前的帳號沒有權限；訊息會附上目前授權的帳號 email | 確認 ID 或網址；接受資料夾的分享邀請；或登出後改用有權限的帳號授權 |
| `OUTSIDE_ROOT` | 目標不在設定的資料夾範圍內 | 只能讀範圍內的檔案。需要其他資料夾時，修改 `DRIVE_READER_ROOT_FOLDER` |
| `NOT_A_FILE` | 要讀取的是資料夾 | 先列出資料夾，再讀其中的檔案 |
| `BROKER_UNREACHABLE` | 連不到換 token 的後端；訊息會附上後端網址 | 確認網路；確認 `DRIVE_READER_BROKER_URL` |
| `GOOGLE_API_ERROR` | Google Drive 回傳其他錯誤 | 稍後再試 |
| `CALLBACK_PORT_UNAVAILABLE` | 設定的固定 port 被其他程式占用 | 換一個 port，或移除這個設定 |

### Token 存放方式

| 東西 | 放在哪裡 | 保護方式 |
|---|---|---|
| refresh token | 你的電腦：`~/.config/claude-drive-reader/credentials.json`（Windows 是 `%USERPROFILE%\.config\claude-drive-reader\credentials.json`） | macOS、Linux：檔案權限 `0600`、資料夾 `0700`，以原子替換寫入，不會寫到一半。Windows：位於使用者設定檔目錄下，由預設的 ACL 保護（只有你的帳號能存取），程式不另外設定 ACL |
| access token | 只在 MCP server 的記憶體中，一小時內有效 | 不寫入任何檔案；快過期時自動透過後端更新 |
| client secret | 只在後端的 Google Cloud Secret Manager | 不在 plugin、不在 repo，你的電腦上也沒有 |

檔案裡只有 refresh token、權限範圍、取得時間三個欄位。後端不保存任何 token 或授權碼。完整的考量見[架構說明](docs/architecture.md#token-保存)。

### 登出與解除安裝

- 說「**登出**」：先向 Google 撤銷授權，再刪除本機的授權檔。撤銷失敗時仍會刪檔，並告訴你可以到 [Google 帳號的第三方存取權頁面](https://myaccount.google.com/permissions) 手動移除。
- 解除安裝 plugin **不會**刪除授權檔。請先登出，再執行：
  ```bash
  claude plugin uninstall drive-reader@drive-reader-marketplace
  ```

### 疑難排解

| 狀況 | 處理 |
|---|---|
| `/mcp` 顯示 `plugin:drive-reader:drive` failed | 多半是找不到 `uv`。確認終端機中 `uv --version` 可以執行，然後**完全重啟** Claude Code（Desktop 要從系統匣結束再開） |
| `/mcp` 顯示 `connection timed out after 30000ms` | 執行環境還沒裝好，Claude Code 在 30 秒內做不完安裝。見下方[啟動逾時](#啟動逾時) |
| Windows：`claude` 顯示 `is not recognized` | Claude Code 的安裝程式不會修改 PATH。執行下面兩行後重開 PowerShell：<br>`$p = [Environment]::GetEnvironmentVariable('PATH', 'User')`<br>`[Environment]::SetEnvironmentVariable('PATH', "$p;$env:USERPROFILE\.local\bin", 'User')` |
| 瀏覽器沒有自動開啟 | 手動點 Claude 顯示的授權網址，結果相同 |
| 同意後瀏覽器顯示「無法連上 127.0.0.1」 | 授權已逾時（超過 5 分鐘），或 Claude Code 在另一台電腦上。重新授權 |
| Claude Code 跑在 SSH 遠端機器上 | 授權結果會送回瀏覽器那台電腦的 `127.0.0.1`，到不了遠端。進階做法：在遠端設定 `DRIVE_READER_CALLBACK_PORT=53682`，連線時加上 `ssh -L 53682:127.0.0.1:53682 <遠端>` 轉送這個 port |
| 想換 Google 帳號 | 說「登出」，再說「幫我授權」，選另一個帳號 |

#### 啟動逾時

通常是跳過了[安裝 plugin](#2-安裝-plugin)裡「先把執行環境裝好」那一步，或更新 plugin 之後沒有重做。Claude Code 逾時會中止安裝，下載到一半的檔案不會保留，所以重連多半還是會逾時。先結束 Claude Code，再用下面任一種方法：

**方法一（建議）：** 在終端機執行[安裝 plugin](#2-安裝-plugin)裡的指令，把環境裝好，再重新開啟 Claude Code。這一步沒有時間限制。

**方法二：** 放寬啟動時限，讓 Claude Code 自己裝完。`MCP_TIMEOUT` 的單位是毫秒，只對這一次啟動有效：

- Windows（PowerShell）：`$env:MCP_TIMEOUT = '180000'; claude`
- macOS、Linux：`MCP_TIMEOUT=180000 claude`

---

## 自行重建

不使用已部署的服務，從零建立自己的 OAuth Client 與後端（Token Broker）。完成後只要把 plugin 的 `DRIVE_READER_BROKER_URL` 指到你的後端。

後端是 FastAPI，部署在 Google Cloud Run。它只做三件需要 client secret 的事：組授權網址、把 Google 回傳的授權碼轉回使用者電腦、代替 plugin 向 Google 換 token。後端沒有資料庫，也不保存任何 token。設計理由見 [ADR 0001](docs/adr/0001-refresh-token-held-locally-stateless-broker.md)。

### 1. 申請自己的 Google Cloud OAuth Client

照 [外部環境申請步驟](docs/setup-gcp-oauth.md) 的階段 A 完成：

1. 建立 GCP 專案並綁定 billing（Cloud Run 的用量在免費額度內，但需要綁定）。
2. 安裝並登入 `gcloud`。
3. 在 Google Search Console 驗證後端要用的網域。
4. 設定 OAuth 同意畫面：首頁與隱私權政策填後端的 `/` 與 `/privacy`；Authorized domains 填你的根網域；Data Access 只加 `https://www.googleapis.com/auth/drive.readonly`。
5. 建立 OAuth Client，類型選 **Web application**。
6. 把 client secret 存進 Secret Manager，名稱 `google-oauth-client-secret`，不要寫進任何檔案。

### 2. 設定 redirect URI

在 Google Cloud Console → **Google Auth Platform** → **Clients** → 你的 Web application client → **Authorized redirect URIs**，加入：

```
https://<你的後端網域>/callback
```

必須和後端的 `PUBLIC_BASE_URL` 加上 `/callback` **完全一致**：`https` 開頭、全部小寫、結尾沒有斜線。後端組授權網址與換 token 時都用這同一個值（實作規格 B5）；不一致時，Google 會在同意畫面前顯示 `redirect_uri_mismatch`。

Authorized JavaScript origins 留空：瀏覽器不會直接呼叫 Google 的 API。

### 3. 部署後端

以下指令在 **repo 根目錄**執行。`<PROJECT_ID>`、`<REGION>`、`<DOMAIN>`、`<CLIENT_ID>` 換成你的值。

```bash
P=<PROJECT_ID>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  secretmanager.googleapis.com drive.googleapis.com logging.googleapis.com iam.googleapis.com --project $P
```

建立專用的 service account，只讓它讀得到那一個 secret：

```bash
gcloud iam service-accounts create token-broker --display-name "Drive Reader Token Broker" --project $P
gcloud secrets add-iam-policy-binding google-oauth-client-secret --project $P \
  --member "serviceAccount:token-broker@$P.iam.gserviceaccount.com" --role roles/secretmanager.secretAccessor
```

從原始碼建置需要預設的 compute service account 有建置權限（只影響建置，執行時用上面的專用帳號）：

```bash
N=$(gcloud projects describe $P --format="value(projectNumber)")
gcloud projects add-iam-policy-binding $P \
  --member "serviceAccount:$N-compute@developer.gserviceaccount.com" --role roles/run.builder
```

部署。`--source backend` 會用 `backend/Dockerfile` 建置映像檔（`uv sync --locked --no-dev`，lockfile 不一致時建置直接失敗）：

```bash
gcloud run deploy token-broker \
  --source backend \
  --project $P --region <REGION> \
  --service-account token-broker@$P.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_CLIENT_ID=<CLIENT_ID>,PUBLIC_BASE_URL=https://<DOMAIN>" \
  --set-secrets "GOOGLE_CLIENT_SECRET=google-oauth-client-secret:latest" \
  --min-instances 0 --max-instances 2
```

| 環境變數 | 內容 |
|---|---|
| `GOOGLE_CLIENT_ID` | OAuth Client ID（不是機密） |
| `PUBLIC_BASE_URL` | 後端對外的網址，不含結尾斜線，例如 `https://drive-auth.example.com` |
| `GOOGLE_CLIENT_SECRET` | 從 Secret Manager 掛入，不出現在指令或 revision 設定的明文中 |

缺少任何一個時，後端會啟動失敗，log 只列出缺少的變數名稱。

綁定自訂網域，再依指令輸出的 DNS 記錄在你的 DNS 服務新增 CNAME（Cloudflare 要設成 DNS only）。憑證約一小時內自動簽發：

```bash
gcloud beta run domain-mappings create --service token-broker --domain <DOMAIN> --region <REGION> --project $P
```

**在第一次真實授權之前**，設定 Cloud Logging 的排除規則。Cloud Run 平台的請求記錄會保存完整網址，包含 `/callback?code=…` 的授權碼；後端程式本身不記 query string，但平台這一層只能用排除規則關掉：

```bash
gcloud logging sinks update _Default --project $P \
  --add-exclusion='name=exclude-broker-callback,filter=resource.type="cloud_run_revision" AND resource.labels.service_name="token-broker" AND httpRequest.requestUrl:"/callback"'
```

排除規則約 5 分鐘後生效，之後再進行第一次授權。

確認後端正常：

```bash
curl https://<DOMAIN>/health
```

應回傳 `ok`。最後到 Google Auth Platform 的 **Audience** 頁按 **Publish app**，讓不在 test users 名單上的帳號也能授權（會看到前面提到的未驗證警告，但可以繼續）。

### 4. 讓 plugin 使用你的後端

把 `DRIVE_READER_BROKER_URL` 設成 `https://<DOMAIN>`（設定方式見[設定](#設定)），重新啟動 Claude Code 後重新授權。

---

## 開發

```
backend/   Token Broker（FastAPI，部署在 Cloud Run）
plugin/    Claude Code plugin：MCP server（Python，stdio）
  src/local_authorization/  授權流程、授權保存、提供 access token
  src/drive_reading/        Root Folder 邊界、列出、依類型讀取內容
  src/mcp_server/           MCP tools、錯誤訊息格式、組裝與設定
docs/      規格、架構說明、ADR、驗證紀錄
.claude-plugin/marketplace.json  讓 repo 本身就是 plugin marketplace
```

兩個專案各自執行測試與依賴規則檢查（import-linter）：

```bash
cd backend && uv sync --locked && uv run pytest && uv run lint-imports
```

```bash
cd plugin && uv sync --locked && uv run pytest && uv run lint-imports
```

測試不連真實的 Google；Google 與 Drive 都以模擬的 HTTP 回應取代。CI 在 Ubuntu、macOS、Windows 上執行上面兩組測試，另外用和 `.mcp.json` 相同的指令啟動 MCP server，透過 MCP 握手確認打包正確。

本機執行後端（需要真實的 OAuth Client）：把 `backend/.env.example` 的三個變數設成環境變數後，

```bash
cd backend && uv run uvicorn token_broker.main:create_app_from_env --factory --port 8080
```

### 文件

| 文件 | 內容 |
|---|---|
| [架構說明](docs/architecture.md) | 元件與資料流、OAuth flow 的選擇、token 保存、各檔案類型的處理、trade-off、已知限制 |
| [實作規格](docs/implementation-spec.md) | bounded contexts、規則編號（B、A、R）、公開合約（C1–C5） |
| [ADR 0001](docs/adr/0001-refresh-token-held-locally-stateless-broker.md) | 為什麼 refresh token 存在本機、後端無狀態 |
| [驗證紀錄](docs/verification.md) | 每個階段的測試清單與真實驗收結果 |
| [名詞表](CONTEXT.md) | 專案用語 |
| [作業規格整理](docs/README.md) | 原始作業說明的整理與需求追蹤清單 |
