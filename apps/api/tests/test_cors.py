"""ADR 0048. Two-pronged: a whitebox check that the real app wires
CORSMiddleware with the documented, settings-driven configuration, plus a
focused behavioral test of CORSMiddleware itself against a real cross-origin
request/response - built as its own minimal app rather than reusing
lorenzo_api.main.create_app(), since that re-registers a global
OpenTelemetry TracerProvider and isn't meant to be called more than once per
process (see configure_tracing).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from httpx import ASGITransport, AsyncClient

from lorenzo_api.config import get_settings
from lorenzo_api.main import app


def test_app_wires_cors_middleware_from_settings() -> None:
    cors_entries = [m for m in app.user_middleware if m.cls is CORSMiddleware]
    assert len(cors_entries) == 1
    kwargs = cors_entries[0].kwargs
    assert kwargs["allow_origins"] == get_settings().cors_allowed_origins
    assert kwargs["allow_credentials"] is False
    assert kwargs["allow_methods"] == ["*"]
    assert kwargs["allow_headers"] == ["*"]
    assert kwargs["expose_headers"] == ["ETag", "Location"]


def test_default_settings_allow_no_origins_at_all() -> None:
    """The fail-closed default (ADR 0048) - confirmed directly against
    Settings rather than assumed, since get_settings() is cached and this
    test suite never sets CORS_ALLOWED_ORIGINS.
    """
    assert get_settings().cors_allowed_origins == []


async def test_healthz_carries_no_cors_headers_by_default() -> None:
    """The real app, real default settings (empty allow_origins) - a
    cross-origin request gets no Access-Control-Allow-Origin at all, so a
    browser blocks it, matching the fail-closed default.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz", headers={"Origin": "https://example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


async def test_cors_middleware_allows_configured_origin_and_exposes_headers() -> None:
    """A standalone app configured exactly per ADR 0048's own parameters,
    but with a real allow_origins entry - proves CORSMiddleware itself
    behaves as documented (allowed origin echoed back, ETag/Location
    exposed) independent of which settings the shared app happens to be
    running with.
    """
    allowed_origin = "https://lorenzo.example.com"
    test_app = FastAPI()
    test_app.add_middleware(
        CORSMiddleware,
        allow_origins=[allowed_origin],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["ETag", "Location"],
    )

    @test_app.get("/ping")
    async def ping() -> dict[str, str]:
        return {"status": "ok"}

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        allowed_response = await client.get("/ping", headers={"Origin": allowed_origin})
        disallowed_response = await client.get("/ping", headers={"Origin": "https://evil.example"})

    assert allowed_response.status_code == 200
    assert allowed_response.headers["access-control-allow-origin"] == allowed_origin
    exposed = allowed_response.headers["access-control-expose-headers"]
    assert "ETag" in exposed
    assert "Location" in exposed

    assert disallowed_response.status_code == 200
    assert "access-control-allow-origin" not in disallowed_response.headers
