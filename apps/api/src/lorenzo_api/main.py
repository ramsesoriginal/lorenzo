from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_pagination import add_pagination
from fastapi_pagination.utils import disable_installed_extensions_check
from prometheus_fastapi_instrumentator import Instrumentator

from lorenzo_api.compression import GzipForPathsMiddleware
from lorenzo_api.config import get_settings
from lorenzo_api.db import engine
from lorenzo_api.errors import register_error_handlers
from lorenzo_api.forwarded_scheme import ForwardedSchemeMiddleware
from lorenzo_api.logging import configure_logging
from lorenzo_api.observability.health import router as health_router
from lorenzo_api.observability.tracing import configure_tracing
from lorenzo_api.release_fanout import start_sweeping, stop_sweeping
from lorenzo_api.repository_quotas import install as install_repository_quotas
from lorenzo_api.routers.activity_log import router as activity_log_router
from lorenzo_api.routers.admin import router as admin_router
from lorenzo_api.routers.app_links import router as app_links_router
from lorenzo_api.routers.beings import router as beings_router
from lorenzo_api.routers.calendar_imports import router as calendar_imports_router
from lorenzo_api.routers.calendar_observances import router as calendar_observances_router
from lorenzo_api.routers.calendar_period_reads import router as calendar_period_reads_router
from lorenzo_api.routers.calendar_periods import router as calendar_periods_router
from lorenzo_api.routers.calendar_references import router as calendar_references_router
from lorenzo_api.routers.calendars import router as calendars_router
from lorenzo_api.routers.campaign_invites import router as campaign_invites_router
from lorenzo_api.routers.campaigns import router as campaigns_router
from lorenzo_api.routers.characters import router as characters_router
from lorenzo_api.routers.clock_relationships import router as clock_relationships_router
from lorenzo_api.routers.clocks import router as clocks_router
from lorenzo_api.routers.computed_stats import router as computed_stats_router
from lorenzo_api.routers.discover import router as discover_router
from lorenzo_api.routers.entities import router as entities_router
from lorenzo_api.routers.entity_export import router as entity_export_router
from lorenzo_api.routers.entity_stats import router as entity_stats_router
from lorenzo_api.routers.event_learning import router as event_learning_router
from lorenzo_api.routers.event_order import router as event_order_router
from lorenzo_api.routers.events import router as events_router
from lorenzo_api.routers.groups import router as groups_router
from lorenzo_api.routers.information import router as information_router
from lorenzo_api.routers.invites import router as invites_router
from lorenzo_api.routers.item_instances import router as item_instances_router
from lorenzo_api.routers.items import router as items_router
from lorenzo_api.routers.knowledge import router as knowledge_router
from lorenzo_api.routers.link_previews import router as link_previews_router
from lorenzo_api.routers.locations import router as locations_router
from lorenzo_api.routers.manuscript_extraction import router as manuscript_extraction_router
from lorenzo_api.routers.manuscript_moves import router as manuscript_moves_router
from lorenzo_api.routers.manuscript_splits import router as manuscript_splits_router
from lorenzo_api.routers.payloads import router as payloads_router
from lorenzo_api.routers.personal_tokens import router as personal_tokens_router
from lorenzo_api.routers.pictures import router as pictures_router
from lorenzo_api.routers.players import router as players_router
from lorenzo_api.routers.public_repositories import router as public_repositories_router
from lorenzo_api.routers.repositories import router as repositories_router
from lorenzo_api.routers.repository_flips import router as repository_flips_router
from lorenzo_api.routers.repository_preview import (
    library_router as repository_preview_library_router,
)
from lorenzo_api.routers.repository_preview import owner_router as repository_showcase_router
from lorenzo_api.routers.repository_preview import (
    visitor_router as repository_preview_visitor_router,
)
from lorenzo_api.routers.repository_profiles import router as repository_profiles_router
from lorenzo_api.routers.stats import router as stats_router
from lorenzo_api.routers.tenant_invites import router as tenant_invites_router
from lorenzo_api.routers.tenants import router as tenants_router
from lorenzo_api.routers.users import router as users_router
from lorenzo_api.routers.writing import router as writing_router
from lorenzo_api.routers.writing_reviews import router as writing_reviews_router

install_repository_quotas()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Finish the announcements a process before this one left half sent (ADR 0301), off the
    # start-up path.
    start_sweeping()
    yield
    await stop_sweeping()
    await engine.dispose()


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

    # See ADR 0048. allow_credentials=False - this API is bearer-token
    # authenticated (ADR 0023), not cookie-based, so a client attaches its
    # token itself rather than relying on the browser's credentialed-request
    # mode. expose_headers is the easy-to-miss part: browsers only expose a
    # small built-in safelist to cross-origin JS by default, which excludes
    # both ETag (ADR 0042's whole concurrency-token mechanism) and Location
    # (every 201 response, ADR 0032) - without listing them explicitly, a
    # cross-origin browser client's requests would succeed while silently
    # being unable to read either header.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_settings().cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag", "Location"],
    )

    # ADR 0262: gzip, for the one response big enough to need it.
    app.add_middleware(GzipForPathsMiddleware, path_suffixes=("/entities/export",))

    # The scheme the client used, for the URLs the API writes; Cloud Run speaks plain HTTP to it.
    app.add_middleware(ForwardedSchemeMiddleware)

    register_error_handlers(app)
    from lorenzo_api.routers.story_sessions import my_router as my_sessions_router
    from lorenzo_api.routers.story_sessions import router as story_sessions_router

    app.include_router(my_sessions_router)
    from lorenzo_api.routers.lived_order import router as lived_order_router
    from lorenzo_api.routers.session_play import router as session_play_router
    from lorenzo_api.routers.story_context import router as story_context_router

    app.include_router(lived_order_router)
    app.include_router(session_play_router)
    app.include_router(story_context_router)
    app.include_router(story_sessions_router)
    app.include_router(health_router)
    app.include_router(app_links_router)
    app.include_router(admin_router)
    app.include_router(activity_log_router)
    app.include_router(users_router)
    app.include_router(personal_tokens_router)
    app.include_router(tenants_router)
    app.include_router(repositories_router)
    app.include_router(repository_profiles_router)
    app.include_router(repository_flips_router)
    app.include_router(public_repositories_router)
    app.include_router(repository_preview_visitor_router)
    app.include_router(repository_preview_library_router)
    app.include_router(repository_showcase_router)
    app.include_router(discover_router)
    app.include_router(campaigns_router)
    app.include_router(campaign_invites_router)
    app.include_router(invites_router)
    app.include_router(tenant_invites_router)
    app.include_router(players_router)
    app.include_router(characters_router)
    app.include_router(writing_router)
    app.include_router(manuscript_moves_router)
    app.include_router(manuscript_splits_router)
    app.include_router(manuscript_extraction_router)
    app.include_router(writing_reviews_router)
    app.include_router(beings_router)
    app.include_router(calendars_router)
    app.include_router(clocks_router)
    app.include_router(locations_router)
    app.include_router(clock_relationships_router)
    app.include_router(calendar_references_router)
    app.include_router(calendar_periods_router)
    app.include_router(calendar_period_reads_router)
    app.include_router(event_order_router)
    app.include_router(events_router)
    app.include_router(event_learning_router)
    app.include_router(calendar_observances_router)
    app.include_router(calendar_imports_router)
    app.include_router(payloads_router)
    app.include_router(pictures_router)
    # Before entities_router: its /{entity_id} would take "export" (ADR 0262).
    app.include_router(entity_export_router)
    app.include_router(entities_router)
    app.include_router(link_previews_router)
    app.include_router(entity_stats_router)
    app.include_router(computed_stats_router)
    app.include_router(groups_router)
    from lorenzo_api.routers.manuscripts import router as manuscripts_router

    app.include_router(manuscripts_router)
    app.include_router(information_router)
    app.include_router(items_router)
    app.include_router(item_instances_router)
    app.include_router(knowledge_router)
    app.include_router(stats_router)

    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    # Stashed on app.state so tests can attach their own span processor
    # (an InMemorySpanExporter) to inspect real spans - see test_tracing.py.
    app.state.tracer_provider = configure_tracing(app)

    add_pagination(app)
    # The tenant-roster route (ADR 0031) deliberately paginates an
    # already-fetched, heterogeneous Python list (three genuinely different
    # row shapes combined) via plain paginate(), not apaginate() - there is
    # no single SQL statement to hand the sqlalchemy extension. Silences the
    # library's own generic "sqlalchemy is installed, did you mean to use
    # its extension?" nudge, which doesn't apply to that one deliberate case.
    disable_installed_extensions_check()

    return app


app = create_app()
