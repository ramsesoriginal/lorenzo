from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from fastapi_pagination import add_pagination
from prometheus_fastapi_instrumentator import Instrumentator

from lorenzo_api.errors import register_error_handlers
from lorenzo_api.logging import configure_logging
from lorenzo_api.observability.health import router as health_router
from lorenzo_api.observability.tracing import configure_tracing
from lorenzo_api.routers.entities import router as entities_router
from lorenzo_api.routers.item_instances import router as item_instances_router
from lorenzo_api.routers.items import router as items_router
from lorenzo_api.routers.payloads import router as payloads_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lorenzo API",
        version=version("lorenzo-api"),
        lifespan=lifespan,
        # Every route handler in this app has a unique function name, so it
        # alone is a clean operationId - FastAPI's own default instead bakes
        # the full templated path in too (e.g.
        # "list_entities_tenants__tenant_id__entities_get"), which is ugly
        # and needlessly unstable for any client codegen against this API.
        generate_unique_id_function=lambda route: route.name,
    )

    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(payloads_router)
    app.include_router(entities_router)
    app.include_router(items_router)
    app.include_router(item_instances_router)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    # Stashed on app.state so tests can attach their own span processor
    # (an InMemorySpanExporter) to inspect real spans - see test_tracing.py.
    app.state.tracer_provider = configure_tracing(app)

    add_pagination(app)

    return app


app = create_app()
