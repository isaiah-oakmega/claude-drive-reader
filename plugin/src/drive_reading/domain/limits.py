"""Drive Reading 的參數值（實作規格 R1、R3、R7、「參數值」）。"""

# R1：從目標往上追溯 parents 最多 20 層。正常的資料夾不會這麼深；
# 設上限是為了不讓異常的結構（例如循環）讓一次請求變成無限多次 API 呼叫。
MAX_ANCESTOR_DEPTH = 20

# R3：遞迴列出最多 5 層、500 筆。超過時截斷並註明，避免一次回傳的內容塞爆 Claude 的 context。
MAX_LIST_DEPTH = 5
MAX_LIST_ITEMS = 500

# R7：GET 類的呼叫遇到 429 或 5xx，等 1 秒、2 秒後各重試一次（共 2 次）。
RETRY_DELAYS_SECONDS = (1.0, 2.0)

# R4：呼叫 Drive 的逾時，連線 10 秒、讀取 30 秒，和 Local Authorization 的值相同。
HTTP_CONNECT_TIMEOUT_SECONDS = 10.0
HTTP_READ_TIMEOUT_SECONDS = 30.0

# R4：交付給 Claude 的內容上限。
# 下載最多 20MB：在下載前看 size，下載中也逐段累計（Google 原生文件的 export 沒有 size）。
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
# 文字最多 50,000 字。
MAX_TEXT_CHARS = 50_000
# 結果裡有影像時，文字只留 10,000 字：Claude Code 對含影像的 tool 結果只有 25,000 token 的上限，
# 不會像純文字結果那樣改存成檔案；5 張 1568px 的頁面影像約 11,000 token，剩下的留給文字。
MAX_TEXT_CHARS_WITH_IMAGES = 10_000
# PDF 整份文件合計最多算繪 5 頁。
MAX_RENDERED_PAGES = 5
# 圖片與算繪頁面的長邊上限：Claude 處理圖片時會把長邊縮到這個大小，先縮好可以省下傳輸量。
MAX_IMAGE_SIDE = 1568

# R4a：一頁抽出的非空白字元少於 20 個，就當成沒有文字層（掃描頁），改算繪成影像。
# 頁碼、頁首這類零星文字不會超過這個數量。
MIN_TEXT_CHARS_PER_PAGE = 20
