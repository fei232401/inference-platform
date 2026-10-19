import httpx
import pytest

from src import main


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_ready_checks_database_readiness(monkeypatch):
    original = httpx.AsyncClient
    seen = []

    def downstream(request):
        seen.append(request.url.path)
        return httpx.Response(503, json={"status": "degraded"})

    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(downstream), **kwargs))
    async with original(transport=httpx.ASGITransport(app=main.app), base_url="http://router") as client:
        response = await client.get("/readyz")
    assert response.status_code == 503
    assert seen == ["/readyz"]


@pytest.mark.anyio
async def test_route_rejects_missing_key():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://router") as client:
        response = await client.post("/v1/route", json={"model_name": "model", "prompt": "hello"})
    assert response.status_code == 401


@pytest.mark.anyio
async def test_control_plane_failure_is_service_unavailable(monkeypatch):
    original = httpx.AsyncClient

    def downstream(request):
        raise httpx.ConnectError("offline", request=request)

    monkeypatch.setattr(main.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(downstream), **kwargs))
    async with original(transport=httpx.ASGITransport(app=main.app), base_url="http://router") as client:
        response = await client.post("/v1/route", headers={"X-API-Key": "test"}, json={"model_name": "model", "prompt": "hello"})
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "control_plane_unavailable"
