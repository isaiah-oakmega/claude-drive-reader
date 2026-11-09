# Drive Reader

讓使用者在 Claude Code 中以自然語言讀取指定 Google Drive 資料夾內容的 plugin，以及支撐它的授權鏈路。

## Language

### 讀取範圍

**Root Folder**:
plugin 設定的單一 Drive 資料夾，是所有列出與讀取的存取邊界；只有位於其子樹內的項目可被存取。預設為出題方提供的測試資料夾。
_Avoid_: 指定資料夾、target folder、default folder

**Read Limitation**:
檔案已成功取得、但內容無法完整交付給 Claude 的情況（不支援的類型、過大、被截斷、無文字層改以頁面影像呈現）。屬於讀取的正常結果，不是 Failure。
_Avoid_: 讀取錯誤、parse error

**Failure**:
存取路徑走不通、使用者需採取行動才能繼續的情況（未授權、授權失效、無權限、超出 Root Folder、Broker 或 Google 無法使用）。
_Avoid_: exception、error（泛稱時）

### 授權

**Authorization Attempt**:
一次進行中的授權嘗試，由 `state`、PKCE verifier 與本機 loopback listener 組成；短效、一次性，同時最多一個。
_Avoid_: login session, auth session

**Token Broker**:
自架的無狀態後端，唯一職責是持有 client secret，代為完成 auth code 換 token 與 refresh；不保存任何使用者 token。
_Avoid_: auth server, proxy, backend（泛稱時）

**Local Credential**:
存在使用者本機的 refresh token（及快取的 access token），是使用者授權的唯一持久紀錄。
_Avoid_: session, session id

**Code Relay**:
Token Broker 的 callback 將 Google 回傳的 auth code 原樣轉交到本機 loopback 的那一步；轉交的是 code，不是 token。
_Avoid_: token handoff, token delivery
