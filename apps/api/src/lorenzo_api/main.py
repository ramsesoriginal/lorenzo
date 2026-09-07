from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi_pagination import add_pagination
from prometheus_fastapi_instrumentator import Instrumentator

from lorenzo_api.errors import register_error_handlers
from lorenzo_api.logging import configure_logging
from lorenzo_api.observability.health import router as health_router
from lorenzo_api.observability.tracing import configure_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Lorenzo API", version="0.1.0", lifespan=lifespan)

    register_error_handlers(app)
    app.include_router(health_router)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    # Stashed on app.state so tests can attach their own span processor
    # (an InMemorySpanExporter) to inspect real spans - see test_tracing.py.
    app.state.tracer_provider = configure_tracing(app)

    # No endpoint returns Page[...] yet - there's no list endpoint at all.
    # Wired now so the first one that needs it doesn't need this step too.
    add_pagination(app)

    return app


app = create_app()
