"""Token Broker 的參數值（實作規格「參數值」）。"""

# 呼叫 Google token endpoint 的逾時：連線 10 秒、讀取 30 秒。
# 不設逾時的話，Google 卡住時 Cloud Run 的請求會一直佔著，本機也會一直等不到結果。
HTTP_CONNECT_TIMEOUT_SECONDS = 10.0
HTTP_READ_TIMEOUT_SECONDS = 30.0
