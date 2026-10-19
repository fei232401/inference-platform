from httpx import ASGITransport, AsyncClient

from src.main import create_app


async def test_custom_app_auth_cannot_fall_back_to_global_settings(database, settings):
    secured = settings.model_copy(update={"auth_required": True})
    app = create_app(secured)
    app.state.database = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/backends")
    assert response.status_code == 401


async def test_custom_schema_version_is_used_by_readiness(database, settings):
    mismatched = settings.model_copy(update={"expected_schema_version": 999})
    app = create_app(mismatched)
    app.state.database = database
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/readyz")
    assert response.status_code == 503
    assert "schema_version_mismatch" in response.json()["failed"]
