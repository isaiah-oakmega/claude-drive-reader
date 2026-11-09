# 0001 Refresh token 存在本機，後端為無狀態 Token Broker

- 狀態：Accepted
- 日期：2026-11-09

## 背景

Google Web application OAuth Client 換 token 與 refresh 都需要 client secret，secret 只能放後端，因此每次 refresh 都必須經過後端。待決定的是 refresh token 存在哪裡。

## 決定

Refresh token 存在使用者本機（`0600` 檔案）。後端是無狀態的 Token Broker：

1. 本機在 OS 分配的隨機 port 開 loopback listener，產生 PKCE verifier 與 `state = <port>.<隨機值>`，開瀏覽器到後端 `/authorize?state&code_challenge`；後端補上 `client_id`、`redirect_uri`（指向自己的 `/callback`）、`scope` 後 302 到 Google。所有 OAuth Client 設定只存在後端，本機只需知道後端網址。
2. 後端 `/callback` 不換 token，從 `state` 解析出 port，只把 `code`、`state` 302 轉交到 `http://127.0.0.1:<port>/callback`（Code Relay）。host 寫死、port 須為 1024–65535 的整數，格式不合即回錯誤頁，因此後端不是 open redirect。`state` 的隨機部分只由本機比對。
3. 本機驗 `state`，把 `code` + `code_verifier` POST 到後端 `/token`；後端附上 secret 向 Google 換 token 並回傳。
4. Refresh 同樣經由 `/token`（`grant_type=refresh_token`）。

後端不持久化、不記錄任何 token。登出時本機刪檔並呼叫 Google revoke。

**後端刻意做薄**：後端只做非它不可的事，也就是保管 client secret 並代為換 token。其他工作都在使用者本機的 MCP server 完成：保存 token、呼叫 Drive API、處理 PDF 與圖片。因此後端不保存任何人的 token，也不經手任何檔案內容。token 在換發與 refresh 時會經過後端，但不會被保存。這是安全取捨，不是功能缺漏。

## 考慮過的替代方案

- **後端持有 refresh token，本機只拿 session id**：本機被入侵時，session id 與 refresh token 一樣是 bearer credential，沒有降低風險；反而新增「後端被攻破時所有使用者的 token 一起外洩」的最壞情境，也多出 DB、加密金鑰管理、session 管理等攻擊面。唯一優勢是集中撤銷，但 Google revoke 已經涵蓋這點。
- **Desktop 類型的 OAuth Client，不用後端**（loopback + PKCE，本機直接向 Google 換 token）：Google 正式支援這種做法，技術上可行、系統也最簡單。但 Desktop client 換 token 時仍要送出 `client_secret`，Google 將其視為非機密，可以內嵌在程式裡，等於把 secret 放進公開的 repo。拒絕的理由是需求面的：
  - 出題方來信 C-1 要求「server 以 Django / Flask / FastAPI 任一撰寫」。沒有後端的話，唯一的 server 是以 stdio 執行的 MCP server，不是 web server，這條要求就沒有對象可以滿足。
  - 原作業的「需自行準備」清單明列「用來部署 OAuth callback 與 token 交換邏輯」的後端，D-2 也要求 README 說明「後端部署方式」。
- **厚後端：讀取 Drive 也在後端做**（例如以 FastAPI 實作 remote MCP server，部署在雲端）：驗收者不需在本機安裝任何 runtime，C-1 也被滿足得最徹底。但後端必須保存所有使用者的 Google token（與上一個方案的缺點相同），檔案內容會經過後端，而且要額外實作 MCP 授權規格，讓後端同時扮演 Claude Code 的 OAuth 授權伺服器與 Google 的 OAuth client。程式碼量約多一倍，兩週內風險過高。

## 後果

- 後端可部署在無持久化的平台上，交付後幾乎不需要維運。
- 本機 token 檔外洩等於 refresh token 外洩；以檔案權限、登出指令、README 說明來緩解。
- `/token` 是公開端點，持有 refresh token 的人都能透過它 refresh；這是接受的風險，因為攻擊者必須先拿到本機檔案。
