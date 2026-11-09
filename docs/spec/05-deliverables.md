# 05 交付內容

交付形式：**GitHub Repository**，期限**兩週**。

## D-1 完整原始碼 [必要]

- plugin 本體
- 任何 MCP server 實作
- （推論）後端 OAuth callback／token 交換服務的原始碼也應納入，因為 README 需說明其部署方式，且驗收會「閱讀 repo 程式碼」。

## D-2 `README.md` [必要]

必須涵蓋以下主題，且**全部以你自己申請、自己部署的環境為準，不依賴出題方提供的任何服務**：

| 主題 | 需說明的內容 |
|------|------|
| 安裝步驟 | 如何從 repo 直接安裝 plugin 到 Claude Code |
| OAuth 設定方式 | 如何**申請自己的 Google Cloud OAuth Client** |
| redirect URI 設定 | redirect URI 要設成什麼、在哪裡設定 |
| 後端部署方式 | 後端如何部署（平台、指令、環境變數等） |
| token 存放方式 | token 存在哪裡、如何保護 |

品質要求：

- **[必要]** 「請確保 README 的安裝步驟**足夠清楚**，讓**沒看過你程式碼的人**也能照著裝起來並跑通。」
- 驗收時**你不會在場**，驗收者完全依 README 自行安裝 → README 是驗收成敗的關鍵路徑。
- （推論）建議區分兩種讀者路徑：
  1. **只想使用**：直接用你已部署的後端與 OAuth Client，最短路徑完成安裝與授權。
  2. **想自行重建**：從零申請 OAuth Client、部署自己的後端。

## D-3 架構說明 [必要]

「簡短」架構說明，需包含**技術選擇與理由**，原文舉例：

- 為何選這個 **OAuth flow**
- **token 怎麼保存**
- 有哪些 **trade-off**

（推論）建議另外涵蓋：

- 元件圖與資料流（plugin ↔ MCP server ↔ 後端 ↔ Google）
- OAuth scope 的選擇與理由
- client secret 放在哪裡、為什麼不放在客戶端
- 不同檔案類型（PDF、圖片、Google 原生格式、子資料夾）的讀取策略
- 已知限制與未做的部分（例如刻意不做搜尋／寫入／監聽）

可放在 README 內的章節，或獨立文件（如 `docs/architecture.md`）並由 README 連結。
