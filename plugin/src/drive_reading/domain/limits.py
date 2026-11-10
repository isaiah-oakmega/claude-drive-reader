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
