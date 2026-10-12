"""URLs the API writes use the scheme the client used, behind a proxy that speaks HTTP to it."""

from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from lorenzo_api.forwarded_scheme import ForwardedSchemeMiddleware


def _app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(ForwardedSchemeMiddleware)

    @app.get("/thing/{thing_id}", name="thing")
    async def thing(thing_id: int, request: Request) -> dict[str, str]:
        return {"url": str(request.url_for("thing", thing_id=thing_id))}

    return app


async def _url(headers: dict[str, str]) -> str:
    async with AsyncClient(transport=ASGITransport(app=_app()), base_url="http://api.test") as c:
        return (await c.get("/thing/1", headers=headers)).json()["url"]


async def test_a_url_keeps_the_scheme_the_request_arrived_with_by_default() -> None:
    assert await _url({}) == "http://api.test/thing/1"


async def test_https_forwarded_by_the_proxy_makes_https_urls() -> None:
    assert await _url({"X-Forwarded-Proto": "https"}) == "https://api.test/thing/1"
    # A chain of proxies: the first entry is the client's own.
    assert await _url({"X-Forwarded-Proto": "https, http"}) == "https://api.test/thing/1"


async def test_anything_else_is_ignored() -> None:
    assert await _url({"X-Forwarded-Proto": "javascript"}) == "http://api.test/thing/1"
    assert await _url({"X-Forwarded-Proto": ""}) == "http://api.test/thing/1"
