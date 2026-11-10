# 文件索引

本目錄整理自 OakMega「Take-Home Assignment · Round 2 — Claude Code Plugin：Google Drive Reader」原始作業說明。

## 規格（spec/）

| # | 文件 | 內容 |
|---|------|------|
| 01 | [專案概述](spec/01-overview.md) | 任務目標、期限、交付形式、範圍界定 |
| 02 | [功能需求](spec/02-functional-requirements.md) | OAuth 授權、列出檔案、讀取內容、自然語言互動；非目標 |
| 03 | [測試資料與檔案類型處理](spec/03-test-data.md) | 測試資料夾、PDF／圖片處理要求 |
| 04 | [環境與前置準備](spec/04-environment.md) | 需自行申請／架設的 OAuth Client、帳號、後端 |
| 05 | [交付內容](spec/05-deliverables.md) | Repo 必含項目、README 與架構說明的要求 |
| 06 | [驗收方式](spec/06-acceptance.md) | 驗收流程、評分重點 |
| 07 | [非功能需求與建議項目](spec/07-non-functional.md) | 錯誤處理、Token 保存、README 可讀性 |
| 08 | [實作考量與風險](spec/08-implementation-notes.md) | 原文未明說、但會影響驗收成敗的技術細節（非原文要求） |
| 09 | [需求追蹤清單](spec/09-requirements-checklist.md) | 所有需求的編號清單，供開發與自我驗收勾選 |

## 設計

| 文件 | 內容 |
|------|------|
| [架構說明](architecture.md) | 元件與資料流、OAuth flow 的選擇、token 保存、讀取策略、trade-off、已知限制 |
| [實作規格](implementation-spec.md) | bounded contexts、不變式、公開合約（Broker API、MCP tools）、實作順序、驗證策略 |
| [ADR](adr/) | 難以回頭的架構決策與其取捨 |
| [名詞表](../CONTEXT.md) | 專案的 ubiquitous language |

## 驗證

| 文件 | 內容 |
|------|------|
| [驗證紀錄](verification.md) | 每個階段的 mock 測試、真實驗收結果，以及待使用者驗收的清單 |
| [驗收用測試檔](acceptance-files/README.md) | 上傳到 Root Folder 的測試檔與預期結果 |

## 部署與設定

| 文件 | 內容 |
|------|------|
| [外部環境申請步驟](setup-gcp-oauth.md) | GCP 專案、gcloud、Search Console、OAuth 同意畫面與 Client、Secret Manager 的逐步說明 |

## 標記約定

- **[必要]**：原文明確要求，驗收必看。
- **[建議]**：原文列為「建議但非強制」。
- **[推論]**：原文未直接寫明，由原文要求推導出的注意事項。08 號文件全部屬於此類。

## 原文出處

- 原始檔案：`OakMega Take Home Assignment.html`
- 標題：Take-Home Assignment — Claude Code Plugin (Google Drive Reader)
- 原文結尾：「如有任何關於範圍或環境設定的問題，歡迎隨時提出。」→ 對範圍有疑義時可直接向出題方詢問。
