"""Local Authorization 的參數值（實作規格 A2、C2、「參數值」）。"""

# A2：Authorization Attempt 5 分鐘後過期。使用者開瀏覽器、看警告、按同意，5 分鐘很充裕；
# 時間再長，listener 佔著 port 卻沒人用的風險就越大。
ATTEMPT_TTL_SECONDS = 300.0

# C2：access token 距離過期不到 60 秒就先 refresh，避免拿到 token 後送到 Drive 時剛好過期。
REFRESH_MARGIN_SECONDS = 60.0

# B2 / C5：Code Relay 只接受 1024–65535 的 port（Broker 端同樣檢查）。低於 1024 是系統保留 port。
MIN_CALLBACK_PORT = 1024
MAX_CALLBACK_PORT = 65535

# 呼叫 Broker 與 Google 的逾時：連線 10 秒、讀取 30 秒，和 Broker 呼叫 Google 的值相同。
HTTP_CONNECT_TIMEOUT_SECONDS = 10.0
HTTP_READ_TIMEOUT_SECONDS = 30.0
