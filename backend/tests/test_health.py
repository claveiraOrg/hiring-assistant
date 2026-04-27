import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_settings():
    with patch("app.core.config.settings") as m:
        m.is_production = False
        m.environment = "test"
        m.sentry_dsn = ""
        m.backend_cors_origins = ["http://localhost:3000"]
        yield m


@pytest.mark.asyncio
async def test_health_endpoint():
    with patch("app.core.config.settings") as mock_s:
        mock_s.is_production = False
        mock_s.environment = "test"
        mock_s.sentry_dsn = ""
        mock_s.backend_cors_origins = ["http://localhost:3000"]

        from app.main import app

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
