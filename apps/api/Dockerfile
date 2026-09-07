FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations
RUN uv sync --locked --no-dev

RUN useradd --create-home --uid 1000 appuser
USER appuser

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["fastapi", "run", "src/lorenzo_api/main.py", "--host", "0.0.0.0", "--port", "8000"]
