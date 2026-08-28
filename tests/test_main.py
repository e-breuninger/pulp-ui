"""Covers the app's outbound httpx client rather than pulp_client.py in isolation:
Pulp's gateway 301s http -> https, and without follow_redirects=True every request
500s when PULP_BASE_URL isn't already the exact scheme Pulp expects.
"""

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager

from app.main import app


@pytest.mark.asyncio
@respx.mock
async def test_index_follows_http_to_https_redirect_from_pulp():
    respx.get("http://pulp.example/pulp/api/v3/distributions/").mock(
        return_value=httpx.Response(
            301, headers={"Location": "https://pulp.example/pulp/api/v3/distributions/"}
        )
    )
    respx.get("https://pulp.example/pulp/api/v3/distributions/").mock(
        return_value=httpx.Response(
            200, json={"count": 0, "next": None, "previous": None, "results": []}
        )
    )

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            response = await client.get("/")

    assert response.status_code == 200
