# 外部環境申請步驟（GCP、OAuth、網域）

> 這份文件是給「自己部署一套」的人照著做的逐步說明，也是 README「如何申請自己的 Google Cloud OAuth Client」一節的底稿。
> Google 的 Console 介面偶爾會改版，按鈕名稱可能略有不同；找不到時以頁面上最接近的名稱為準。

## 0. 先決定好這幾個值

後面每一步都會用到。先想好，填在這裡，後面照抄即可。

| 代號 | 說明 | 範例 |
|---|---|---|
| `<網域>` | 你在 Cloudflare 上的根網域 | `example.com` |
| `<子網域>` | Broker 的網址，建議 `drive-auth.<網域>` | `drive-auth.example.com` |
| `<專案ID>` | GCP 專案 ID：6–30 字元，只能用小寫英文、數字、連字號，英文字母開頭，全球唯一，**建立後不能改** | `drive-reader-isaiah` |
| `<你的Gmail>` | 用來建立 GCP 專案、Search Console、接受資料夾邀請的帳號。**全部用同一個帳號** | `you@gmail.com` |

> 以下指令和欄位中的 `<...>` 都要換成你自己的值，**角括號也要刪掉**。

---

## 階段 A：現在就能做

### A1. 建立 GCP 專案並綁定 billing

1. 用 `<你的Gmail>` 登入 https://console.cloud.google.com/
2. 點左上角 Google Cloud 標誌旁邊的**專案選擇器** → 右上角 **New Project**
3. 填寫：
   - **Project name**：`Drive Reader`
   - **Project ID**：點 **Edit**，改成 `<專案ID>`
   - **Location**：沒有組織就維持 `No organization`
4. 按 **Create**，等幾秒鐘後，用專案選擇器切換到這個專案
5. 左側選單 → **Billing** → 如果出現 `This project has no billing account`，按 **Link a billing account**
   - 已有 billing 帳號：直接選擇 → **Set account**
   - 沒有的話：按 **Create billing account**，照指示填寫信用卡。新帳號通常有免費試用額度；本專案的用量在 Cloud Run 免費額度內

✅ 完成條件：專案選擇器顯示 `Drive Reader`，Billing 頁面顯示已連結的 billing 帳號。

### A2. 安裝並登入 gcloud（在這台 Linux 電腦上）

在 terminal 依序執行（Ubuntu／Pop!_OS 的官方 apt 安裝方式）：

```bash
sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates gnupg curl
```

```bash
curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg
```

```bash
echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list
```

```bash
sudo apt-get update && sudo apt-get install -y google-cloud-cli
```

確認安裝成功：

```bash
gcloud --version
```

登入（會開瀏覽器，選 `<你的Gmail>` 並按「允許」）：

```bash
gcloud auth login
```

設定預設專案：

```bash
gcloud config set project <專案ID>
```

確認設定正確：

```bash
gcloud config list
```

✅ 完成條件：`gcloud config list` 顯示的 `account` 是 `<你的Gmail>`，`project` 是 `<專案ID>`。

> 要啟用的 API（Drive、Cloud Run、Secret Manager、Cloud Build、Artifact Registry）之後由 Claude 用 gcloud 處理，這裡不用做。

### A3. 在 Search Console 驗證網域擁有權

Cloud Run 綁定自訂網域、OAuth 同意畫面的 Authorized domains，都會檢查 `<你的Gmail>` 是否擁有這個網域。

1. 用 `<你的Gmail>` 開啟 https://search.google.com/search-console
2. 左上角資源選單 → **新增資源**
3. 選左邊的 **網域**（不是右邊的「網址前置字元」），輸入根網域 `<網域>`（例如 `example.com`，**不要**填子網域，也不要加 `https://`）→ **繼續**
4. 畫面會顯示一段 TXT 記錄，例如 `google-site-verification=AbCdEf...`，按 **複製**
   - 如果畫面提供「透過 Cloudflare 驗證」的按鈕，也可以直接用它自動完成，就能跳過下面第 5 步
5. 另開分頁到 Cloudflare Dashboard → 選 `<網域>` → **DNS** → **Records** → **Add record**：

   | 欄位 | 填入 |
   |---|---|
   | Type | `TXT` |
   | Name | `@` |
   | Content | 剛才複製的 `google-site-verification=...` 整串 |
   | TTL | `Auto` |

   按 **Save**
6. 回到 Search Console 按 **驗證**。如果失敗，等 5–10 分鐘讓 DNS 生效後再按一次

✅ 完成條件：Search Console 顯示「已驗證擁有權」。這筆 TXT 記錄**不要刪除**，刪掉後驗證會失效。

### A4. 設定 OAuth 同意畫面

GCP Console 左側選單 → **APIs & Services** → **OAuth consent screen**（或直接搜尋 **Google Auth Platform**）。

#### 第一次會出現設定精靈（按 **Get started**）

| 步驟 | 欄位 | 填入 |
|---|---|---|
| App Information | App name | `Drive Reader` |
| | User support email | 下拉選單選 `<你的Gmail>` |
| Audience | | 選 **External** |
| Contact Information | Email addresses | `<你的Gmail>` |
| Finish | | 勾選同意 Google API Services: User Data Policy |

最後按 **Create**。

#### Branding 頁（左側選單 **Branding**）

| 欄位 | 填入 |
|---|---|
| App name | `Drive Reader`（已填好） |
| User support email | `<你的Gmail>`（已填好） |
| App logo | **留空**。上傳 logo 會觸發品牌驗證要求 |
| Application home page | `https://<子網域>/` |
| Application privacy policy link | `https://<子網域>/privacy` |
| Application terms of service link | 留空 |
| Authorized domains | 按 **Add domain**，填 `<網域>`（根網域，不含子網域和 `https://`） |
| Developer contact information | `<你的Gmail>` |

按 **Save**。首頁和隱私權政策網址現在還打不開，這是正常的，Broker 上線後就會有頁面。

#### Data Access 頁（左側選單 **Data Access**）

1. 按 **Add or remove scopes**
2. 在篩選框輸入 `drive.readonly`
3. 勾選 `https://www.googleapis.com/auth/drive.readonly`（說明文字類似 *See and download all your Google Drive files*）
4. **其他 scope 一個都不要勾**
5. 按 **Update** → 回到頁面後按 **Save**

✅ 完成條件：`drive.readonly` 出現在 **Your restricted scopes** 區塊。

#### Audience 頁（左側選單 **Audience**）

1. 確認 User type 是 **External**，Publishing status 是 **Testing**
2. **先不要按 Publish app**，等 Broker 上線後再按（階段 B）
3. 在 **Test users** 按 **Add users**，加入 `<你的Gmail>`。這樣在發布前就能先用你的帳號測試授權流程
4. **第二個帳號不要加進來**，它要用來模擬發布後的驗收者

### A5. 建立 OAuth Client

左側選單 → **Clients** → **Create client**

| 欄位 | 填入 |
|---|---|
| Application type | **Web application** |
| Name | `drive-reader-broker`（只是內部名稱） |
| Authorized JavaScript origins | **留空** |
| Authorized redirect URIs | 按 **Add URI**，填 `https://<子網域>/callback`。要完全一致：`https` 開頭、結尾沒有斜線、全部小寫 |

按 **Create**。

⚠️ **畫面會跳出 Client ID 和 Client secret。Client secret 可能只在這個時候完整顯示一次**，關掉之後就看不到了。所以：

1. 先**複製 Client ID**，這個可以給 Claude
2. **複製 Client secret**，直接進行下一步 A6，存進 Secret Manager
3. 如果畫面有 **Download JSON**，也可以先下載當作備份，但存進 Secret Manager 後**要刪除這個檔案**

### A6. 把 client secret 存進 Secret Manager

1. 另開分頁，GCP Console 上方搜尋列輸入 `Secret Manager` 並開啟
2. 如果出現 **Enable** 按鈕，先按下去啟用 API
3. 按 **Create secret**：

   | 欄位 | 填入 |
   |---|---|
   | Name | `google-oauth-client-secret` |
   | Secret value | 貼上 A5 複製的 client secret。前後**不要有空白或換行** |
   | Replication policy | 維持 **Automatic** |
   | 其他選項 | 全部維持預設 |

4. 按 **Create secret**
5. 收尾：
   - 刪除 A5 下載的 JSON 檔（如果有）
   - 隨便複製一段其他文字，覆蓋剪貼簿裡的 secret
   - **不要把 secret 貼到任何對話、文件或 commit 裡**

✅ 完成條件：Secret Manager 列表出現 `google-oauth-client-secret`，版本 1 為 Enabled。

### A7. 接受測試資料夾的分享邀請

1. 用 `<你的Gmail>` 打開出題方寄來的 Google Drive 分享信，點 **開啟**
   - 找不到信的話，到 Google Drive → 左側 **與我共用**，找到那個資料夾
2. 確認網址列的資料夾 ID 是 `1AU6ZW-3NFxme6388YPe98bGWWh9q_E5Y`
3. 確認看得到裡面的 **PDF** 和**圖片**，各點開一次確認可以預覽

✅ 完成條件：用 `<你的Gmail>` 開啟 https://drive.google.com/drive/folders/1AU6ZW-3NFxme6388YPe98bGWWh9q_E5Y 能看到檔案。

### A8. 準備第二個 Google 帳號

- 用來模擬「完全沒看過這個專案的驗收者」
- 這個帳號**不要**：加進 GCP 專案、加進 Test users、接受測試資料夾的邀請
- 用它可以驗證兩件事：
  - 發布後，陌生帳號是否能看到未驗證警告並繼續授權
  - 沒有資料夾權限時，是否回傳 `NOT_FOUND_OR_NO_ACCESS`，並附上正確的帳號 email

---

## 完成後交給 Claude 的資訊

| 項目 | 你的值 |
|---|---|
| GCP 專案 ID | |
| 想用的 region（建議 `asia-east1`，台灣） | |
| Broker 子網域 | |
| OAuth Client ID（`....apps.googleusercontent.com`，不是機密） | |
| Secret Manager 的 secret 名稱 | `google-oauth-client-secret` |

以及確認以下事項都已完成：

- [ ] `gcloud config list` 顯示正確的帳號和專案
- [ ] Search Console 已驗證 `<網域>`
- [ ] 同意畫面：External、只有 `drive.readonly`、`<你的Gmail>` 在 Test users、**尚未 Publish**
- [ ] OAuth Client 的 redirect URI 是 `https://<子網域>/callback`
- [ ] 測試資料夾的邀請已接受，看得到 PDF 和圖片
- [ ] 第二個帳號已準備好

**絕對不要給 Claude 的**：client secret 本身、任何密碼。

---

## 階段 B：Broker 上線後再做（Claude 部署後會提醒你）

### B1. 在 Cloudflare 新增 Cloud Run 的 DNS 記錄

Claude 綁定網域時，Cloud Run 會給出一筆記錄，通常是：

| 欄位 | 填入 |
|---|---|
| Type | `CNAME` |
| Name | 子網域的前綴，例如 `drive-auth` |
| Target | `ghs.googlehosted.com.` |
| Proxy status | **DNS only（灰色雲朵）**。橘色雲朵會讓 Google 無法簽發憑證 |
| TTL | `Auto` |

憑證簽發可能需要 15 分鐘到數小時。

### B2. 發布同意畫面

確認 `https://<子網域>/` 和 `https://<子網域>/privacy` 都能打開之後：

1. Google Auth Platform → **Audience** → **Publish app** → **Confirm**
2. Publishing status 變成 **In production**
3. 頁面可能顯示需要驗證，**不用送出驗證申請**（原因見 [ADR 0001](adr/0001-refresh-token-held-locally-stateless-broker.md) 與實作規格）。不送驗證時，使用者會看到「Google 尚未驗證這個應用程式」的警告，點「進階」→「前往 Drive Reader（不安全）」即可繼續
