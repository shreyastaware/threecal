# syntax=docker/dockerfile:1
# Threecal API image for Railway. Keep PYTHON_VERSION in sync with backend/.python-version.
ARG PYTHON_VERSION=3.10

FROM ghcr.io/astral-sh/uv:0.8.13 AS uv

FROM python:${PYTHON_VERSION}-slim AS builder
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# Install dependencies first so code changes don't invalidate this layer.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

FROM python:${PYTHON_VERSION}-slim AS runtime
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    ENVIRONMENT=production \
    AUTO_CREATE_TABLES=false \
    DATA_DIR=/data \
    PORT=8000
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app
WORKDIR /app
COPY --from=builder --chown=app:app /app /app
RUN chmod +x /app/docker-entrypoint.sh

EXPOSE 8000
# The entrypoint starts as root only to fix ownership of the Railway volume (mounted as root),
# then drops to the unprivileged `app` user before running the command.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*' --no-access-log"]
