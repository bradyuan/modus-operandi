# MO, hosted. Data lives on a persistent volume at /data (MO_HOME), as the same JSON files as locally.
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy MO_HOME=/data

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev

EXPOSE 8080
# FLY_APP_NAME is set by Fly.io; the public address is <app>.fly.dev.
CMD ["sh", "-c", "exec uv run --no-dev mo-server --public-host ${FLY_APP_NAME}.fly.dev --port 8080 --bind 0.0.0.0"]
