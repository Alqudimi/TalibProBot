FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY src ./src
COPY database.sql ./database.sql
COPY migrations ./migrations
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts

RUN chown -R app:app /app
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD uv run python scripts/check_system.py

CMD ["uv", "run", "python", "-m", "src.app.main"]
