from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator

from lorenzo_api.logging import configure_logging
from lorenzo_api.observability.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Lorenzo API", version="0.1.0", lifespan=lifespan)

    app.include_router(health_router)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    return app


app = create_app()
