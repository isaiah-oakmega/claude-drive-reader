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

## 考慮過的替代方案

- **後端持有 refresh token，本機只拿 session id**：本機被入侵時，session id 與 refresh token 一樣是 bearer credential，沒有降低風險；反而新增「後端被攻破時所有使用者的 token 一起外洩」的最壞情境，也多出 DB、加密金鑰管理、session 管理等攻擊面。唯一優勢是集中撤銷，但 Google revoke 已經涵蓋這點。
- **Desktop loopback flow，不用後端**：不符合題目「自架後端部署 callback 與 token 交換」的預期。

## 後果

- 後端可部署在無持久化的平台上，交付後幾乎不需要維運。
- 本機 token 檔外洩等於 refresh token 外洩；以檔案權限、登出指令、README 說明來緩解。
- `/token` 是公開端點，持有 refresh token 的人都能透過它 refresh；這是接受的風險，因為攻擊者必須先拿到本機檔案。
