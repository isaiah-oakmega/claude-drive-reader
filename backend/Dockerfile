# Token Broker 的映像檔。Cloud Run 以 PORT 環境變數告訴容器要監聽哪個 port。
FROM python:3.12-slim

# 固定 uv 版本，建置結果不會因為 uv 改版而變動
COPY --from=ghcr.io/astral-sh/uv:0.12.1 /uv /bin/uv

WORKDIR /app

# 先預先編譯 .pyc，縮短冷啟動；copy 模式避免在容器檔案系統上建立 hardlink 失敗
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

# 先只複製依賴宣告並安裝依賴：程式碼改動時這一層可以沿用快取
# --locked：uv.lock 和 pyproject.toml 不一致就讓建置失敗；--no-dev：不安裝 pytest 等開發工具
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# --factory：由 create_app_from_env() 在啟動時讀環境變數組出 app，缺設定就直接啟動失敗
# --no-access-log：uvicorn 的 access log 會記完整網址（含 /callback 的 auth code），改由 app 自己記（B1）
CMD ["sh", "-c", "exec uvicorn token_broker.main:create_app_from_env --factory --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
