"""Tests for the demo-project health endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from demo_project.main import app


@pytest.mark.asyncio
async def test_health_check() -> None:
    """The health endpoint reports an ok status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
