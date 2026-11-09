# Drive Reader

讓使用者在 Claude Code 中以自然語言讀取指定 Google Drive 資料夾內容的 plugin，以及支撐它的授權鏈路。

## Language

### 讀取範圍

**Root Folder**:
plugin 設定的單一 Drive 資料夾，是所有列出與讀取的存取邊界；只有位於其子樹內的項目可被存取。預設為出題方提供的測試資料夾。
_Avoid_: 指定資料夾、target folder、default folder

### 授權

**Token Broker**:
自架的無狀態後端，唯一職責是持有 client secret，代為完成 auth code 換 token 與 refresh；不保存任何使用者 token。
_Avoid_: auth server, proxy, backend（泛稱時）

**Local Credential**:
存在使用者本機的 refresh token（及快取的 access token），是使用者授權的唯一持久紀錄。
_Avoid_: session, session id

**Code Relay**:
Token Broker 的 callback 將 Google 回傳的 auth code 原樣轉交到本機 loopback 的那一步；轉交的是 code，不是 token。
_Avoid_: token handoff, token delivery
