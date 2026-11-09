# 06 驗收方式

## 前提

- 出題方會**直接在自己的環境**中安裝你交付的 plugin 進行測試，並審閱 repo。
- **不會請你在場操作**，完全依 README 步驟自行安裝。

## 驗收流程（依序）

| 步驟 | 動作 | 對應需求 |
|------|------|------|
| 1 | 從你的 repo **直接安裝** plugin | [D-2 README 安裝步驟](05-deliverables.md#d-2-readmemd-必要) |
| 2 | 完成**一次完整**的 OAuth 授權 | [FR-1](02-functional-requirements.md#fr-1-oauth-授權) |
| 3 | 用自然語言請 Claude「**列出資料夾內的檔案**」 | [FR-2](02-functional-requirements.md#fr-2-列出資料夾內檔案) |
| 4 | 用自然語言請 Claude「**讀出檔案的內容**」 | [FR-3](02-functional-requirements.md#fr-3-讀取檔案內容並回應提問) |
| 5 | 閱讀 repo 程式碼與架構說明 | [D-1](05-deliverables.md#d-1-完整原始碼-必要)、[D-3](05-deliverables.md#d-3-架構說明-必要) |

## 評分重點

1. **OAuth 流程**是否**順暢**、**安全**
2. **讀取路徑**是否**穩定**
3. README 是否讓沒看過程式碼的人能裝起來並跑通

明確**不是**評分重點：repo 裡**程式碼的量**。

## 自我驗收建議 [推論]

- 用一個**乾淨環境**（新的 Claude Code 設定、沒有任何既有 token、沒有本機開發用環境變數）完整照 README 走一遍。
- 用**另一個 Google 帳號**（非 OAuth Client 擁有者）測試授權，模擬驗收者情境。
- 步驟 3、4 的自然語言提問方式不固定，應測試多種說法（例如「這個資料夾有什麼」、「幫我看那個 PDF 寫了什麼」、「圖片裡是什麼」），確認 Claude 都能正確觸發工具。
- 驗收期間（交付後可能持續一段時間）後端與 OAuth Client 必須保持上線。
