FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

WORKDIR /app/apps/api

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY apps/api/pyproject.toml apps/api/uv.lock ./
COPY packages/calendar-engine /app/packages/calendar-engine
COPY packages/map-engine /app/packages/map-engine
RUN uv sync --locked --no-install-project --no-dev

COPY apps/api/src ./src
COPY apps/api/alembic.ini ./
COPY apps/api/migrations ./migrations
COPY apps/api/README.md ./
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 1000 appuser
USER appuser

ENV PATH="/app/apps/api/.venv/bin:$PATH"

EXPOSE 8000
CMD ["sh", "-c", "fastapi run src/lorenzo_api/main.py --host 0.0.0.0 --port ${PORT:-8000}"]
