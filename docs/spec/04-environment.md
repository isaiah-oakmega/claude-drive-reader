# 04 環境與前置準備

## 原則：環境全部自理

> OAuth Client、redirect URI、後端服務（若需要）都由你自己申請、自己架設、自己部署。我們不提供任何正式環境的 credentials 或伺服器。

- 出題方**不提供**：任何正式環境 credentials、任何伺服器。
- README 中的一切設定步驟，必須**以自己申請、自己部署的環境為準，不依賴出題方提供的任何服務**。

## 需自行準備的項目（原文 checklist）

- [ ] **Google Cloud OAuth Client**：自己申請一組（不會提供公司正式環境的 credentials）。
- [ ] **自己的 Google 帳號**：用來接受測試資料夾的分享邀請。
- [ ] **自己的後端／伺服器環境**：用來部署 **OAuth callback** 與 **token 交換邏輯**。
  - 平台不限，可用任何熟悉的平台，原文舉例：自己的 VPS、Cloudflare Workers、Vercel 等。

## 授權鏈路組成

需自行設計並打通的整條鏈路：

```
Google Cloud OAuth Client（自行申請）
        │
        ▼
redirect URI（自行設定，指向自己的後端）
        │
        ▼
後端：OAuth callback + token 交換（自行部署）
        │
        ▼
Token 保存（不可明碼寫死，見 07）
        │
        ▼
Claude Code plugin / MCP server 以 token 呼叫 Google Drive API
```

- 原文寫「後端服務（**若需要**）」：代表後端是否必要取決於你選的 OAuth flow，但「需自行準備」清單又明列「用來部署 OAuth callback 與 token 交換邏輯」的後端環境 → 預期做法是**有自架後端**。若選擇不需後端的方案，需在架構說明中交代理由與 trade-off（見 [05](05-deliverables.md)、[08](08-implementation-notes.md)）。

## 驗收者視角 [推論]

- 驗收者會在**他們自己的環境**安裝 plugin，並以**他們的 Google 帳號**完成授權。
- 因此你部署的後端與 OAuth Client 在驗收期間必須**持續可用**，且必須允許**驗收者的帳號**通過授權（見 [08 OAuth 同意畫面與測試使用者](08-implementation-notes.md#oauth-同意畫面發布狀態)）。
