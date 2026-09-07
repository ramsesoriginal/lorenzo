from httpx import AsyncClient


async def test_unknown_route_returns_rfc9457_problem(client: AsyncClient) -> None:
    response = await client.get("/this-route-does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    body = response.json()
    assert body["status"] == 404
    assert "type" in body
    assert "title" in body
