"""Broker 固定替本機決定的授權參數。本機無法指定這些值。"""

# B4：唯一允許的 scope。唯讀、只到 Drive，符合測試資料夾只給檢視權限的情境（NFR-4）。
SCOPE = "https://www.googleapis.com/auth/drive.readonly"

# access_type=offline 才會拿到 refresh token；
# prompt=consent 讓每次授權都重新發 refresh token，否則 Google 只在第一次同意時才給。
ACCESS_TYPE = "offline"
PROMPT = "consent"

CODE_CHALLENGE_METHOD = "S256"
