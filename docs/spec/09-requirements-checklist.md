# 09 需求追蹤清單

開發與自我驗收用。狀態的依據見[驗證紀錄](../verification.md)（2026-11-16）。標記：**必要**＝原文明確要求；**建議**＝原文「建議但非強制」；**推論**＝由原文推導。

## 功能

| ID | 需求 | 等級 | 來源 | 狀態 |
|----|------|------|------|------|
| FR-1 | 透過 OAuth 完成 Google 帳號授權 | 必要 | §1 | ✅ 階段 2、Part 5 |
| FR-1a | OAuth 流程順暢（驗收者可獨立完成一次完整授權） | 必要 | §3 | ✅ 5-2、5-3 照 README 完成 |
| FR-1b | OAuth 流程安全 | 必要 | §3 | ✅ PKCE、state、log 排除（B1–B6、A1–A7） |
| FR-2 | 列出指定資料夾內的檔案 | 必要 | §1 | ✅ 情境 8 |
| FR-2a | 含子資料夾 | 必要 | §1 | ✅ 情境 8 |
| FR-3 | 讀取檔案內容 | 必要 | §1 | ✅ 階段 4、5-5 |
| FR-3a | 依內容回應自然語言提問 | 必要 | §1 | ✅ 5-5 追問 |
| FR-3b | 讀取路徑穩定 | 必要 | §3 | ✅ R7 重試、情境 16 |
| FR-4 | PDF（非原生 Google 格式）有合理處理，回報「無法解析」亦可 | 必要 | §4 | ✅ 情境 5、6、6a、5-5 |
| FR-5 | 圖片（無法直接抽文字）有合理處理 | 必要 | §4 | ✅ 情境 7、5-5 |
| FR-6 | 以自然語言觸發「列出檔案」 | 必要 | §3-3 | ✅ 階段 5 自然語言 |
| FR-7 | 以自然語言觸發「讀出檔案內容」 | 必要 | §3-4 | ✅ 階段 5 自然語言 |

## 非目標（確認沒有浪費資源）

| ID | 項目 | 狀態 |
|----|------|------|
| OOS-1 | 不做搜尋 | ✅ 只有 list_files、read_file |
| OOS-2 | 不做寫入 | ✅ scope 為 drive.readonly |
| OOS-3 | 不做監聽變更 | ✅ 沒有監聽 |

## 環境

| ID | 需求 | 等級 | 來源 | 狀態 |
|----|------|------|------|------|
| ENV-1 | 自行申請 Google Cloud OAuth Client | 必要 | §1、§5 | ✅ 階段 1b |
| ENV-2 | 自行設定 redirect URI | 必要 | §1 | ✅ 階段 1b |
| ENV-3 | 自行架設並部署後端（OAuth callback + token 交換） | 必要 | §1、§5 | ✅ Cloud Run（階段 1b） |
| ENV-4 | 用自己的 Google 帳號接受資料夾邀請並確認可讀 | 必要 | §5 | ✅ 5-5 |
| ENV-5 | 不依賴出題方提供的任何服務／credentials | 必要 | §1、§2 | ✅ |
| ENV-6 | 驗收者帳號能通過 OAuth（consent screen 發布狀態／test users） | 推論 | §3 | ✅ 已發布；第二帳號授權（5-3） |
| ENV-7 | 交付後後端與 OAuth Client 持續可用、refresh token 不會提早失效 | 推論 | §3 | ✅ 已發布，refresh token 不受 7 天限制；後端保留到評估結束 |

## 交付

| ID | 需求 | 等級 | 來源 | 狀態 |
|----|------|------|------|------|
| D-1 | GitHub repo，含完整原始碼（plugin + MCP server） | 必要 | §2 | ✅ |
| D-1a | 後端原始碼一併納入 | 推論 | §2 | ✅ backend/ |
| D-2 | README：安裝步驟 | 必要 | §2 | ✅ README「快速開始」 |
| D-2a | README：如何申請自己的 Google Cloud OAuth Client | 必要 | §2 | ✅ README「自行重建」1 |
| D-2b | README：redirect URI 設定 | 必要 | §2 | ✅ README「自行重建」2 |
| D-2c | README：後端部署方式 | 必要 | §2 | ✅ README「自行重建」3 |
| D-2d | README：token 存放方式 | 必要 | §2 | ✅ README「Token 存放方式」 |
| D-2e | README 讓沒看過程式碼的人能裝起來並跑通 | 必要 | §3、§6 | ✅ 5-2 沒有需要猜的地方 |
| D-2f | 可從 repo 直接安裝 plugin | 必要 | §3-1 | ✅ 5-2 |
| D-3 | 架構說明：技術選擇與理由 | 必要 | §2 | ✅ architecture.md |
| D-3a | 架構說明：為何選此 OAuth flow | 必要 | §2 | ✅ architecture.md |
| D-3b | 架構說明：token 怎麼保存 | 必要 | §2 | ✅ architecture.md |
| D-3c | 架構說明：trade-off | 必要 | §2 | ✅ architecture.md |
| D-4 | 2026-11-23（一）前交付 | 必要 | 標頭、來信 | ☐ 寄出 repo 網址 |
| D-5 | 交付時 repo 設為 public，交付前掃描 git 歷史確認無 secret | 推論 | §3-1 | ✅ 公開；交付前掃描 |
| C-1 | server 以 Django / Flask / FastAPI 任一撰寫 | 必要 | 來信 | ✅ FastAPI |
| C-2 | 能清楚說明每一行邏輯的功用與技術取捨 | 必要 | 來信 | ☐ 面試時說明（程式已有說明原因的註解） |
| C-3 | repo 中多記錄決策與內容（ADR、名詞表、架構說明） | 建議 | 來信 | ✅ ADR、CONTEXT.md、architecture.md、verification.md |

## 非功能

| ID | 需求 | 等級 | 來源 | 狀態 |
|----|------|------|------|------|
| NFR-1 | 授權失敗時訊息清楚 | 建議 | §6 | ✅ 情境 3、11、12、14 |
| NFR-2 | 檔案無法解析時訊息清楚 | 建議 | §6 | ✅ 讀取限制（階段 4） |
| NFR-3 | Token 保存合理、不過度設計 | 建議 | §6 | ✅ 本機檔案，POSIX 0600 |
| NFR-4 | Token／secret 不明碼寫死 | 建議 | §6 | ✅ Secret Manager |
| NFR-5 | 只要求唯讀 scope（最小權限） | 推論 | §1 | ✅ drive.readonly |

## 自我驗收（模擬 §3 流程）

- [x] 乾淨環境，照 README 從 repo 安裝 plugin
- [x] 用非開發者的 Google 帳號完成一次完整 OAuth
- [x] 自然語言「列出資料夾內的檔案」→ 正確列出，含子資料夾
- [x] 自然語言「讀出檔案的內容」→ PDF 有合理結果
- [x] 自然語言「讀出檔案的內容」→ 圖片有合理結果
- [x] 刻意製造錯誤（未授權、撤銷授權、錯誤 ID）→ 訊息清楚（未授權：情境 1、3；撤銷：情境 12；錯誤 ID 由 Mock 測試涵蓋格式錯誤與 404，真實環境的 404 路徑和情境 11 相同；Root Folder 外的 ID 在階段 3 實測得到 `OUTSIDE_ROOT`）
- [x] 搜尋 repo 確認沒有任何 secret／token 被 commit
