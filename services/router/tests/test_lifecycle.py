import asyncio
import json
import time

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from src import main
from src.admission import AdmissionController
from src.config import Settings
from src.ttft import TTFTWindow


@pytest.fixture
def anyio_backend():
    return "asyncio"


def settings(**changes):
    values = dict(request_timeout_seconds=.5, control_timeout_seconds=.15,
                  upstream_timeout_seconds=.1, audit_timeout_seconds=.05, stream_openai=False)
    return Settings(**(values | changes))


class Downstream:
    def __init__(self):
        self.upstream_delay = 0
        self.control_delay = 0
        self.audit_delay = 0
        self.audit_status = 200
        self.upstream_status = 200
        self.records = []
        self.entered = asyncio.Event()
        self.audit_entered = asyncio.Event()
        self.control_keys = []
        self.stream = None

    async def __call__(self, request):
        path = request.url.path
        if path == "/v1/chat/completions":
            assert "x-api-key" not in request.headers
            self.entered.set()
            await asyncio.sleep(self.upstream_delay)
            if self.stream is not None:
                return httpx.Response(200, stream=self.stream)
            return httpx.Response(self.upstream_status, json={"choices": [{"message": {"content": "OK"}}], "usage": {"completion_tokens": 1}})
        self.control_keys.append(request.headers.get("x-api-key"))
        if path == "/api/v1/requests":
            self.audit_entered.set()
            await asyncio.sleep(self.audit_delay)
            self.records.append(json.loads(request.content))
            return httpx.Response(self.audit_status, json={"request_id": "saved"})
        await asyncio.sleep(self.control_delay)
        if path.endswith("/candidates"):
            return httpx.Response(200, json={"ranked": [{"backend_id": 1, "score": 1, "excluded": False}]})
        return httpx.Response(200, json={"id": 1, "name": "engine", "url": "http://engine", "engine": "openai"})


@pytest.fixture
async def environment(monkeypatch):
    downstream = Downstream()
    monkeypatch.setattr(main, "get_settings", lambda: settings())
    monkeypatch.setattr(main.app.state, "admission", AdmissionController())
    monkeypatch.setattr(main.app.state, "ttft", TTFTWindow())
    monkeypatch.setattr(main.app.state, "audit_tasks", set())
    async with httpx.AsyncClient(transport=httpx.MockTransport(downstream), timeout=None) as client:
        monkeypatch.setattr(main.app.state, "http_client", client, raising=False)
        monkeypatch.setattr(main.app.state, "audit_client", client, raising=False)
        yield downstream


async def route(key="test"):
    return await main.route(main.RouteIn(model_name="model", prompt="hello", policy="least_inflight"), key)


@pytest.mark.anyio
async def test_backend_timeout_releases_capacity_and_records_error(environment):
    environment.upstream_delay = 1
    started = time.perf_counter()
    with pytest.raises(HTTPException) as caught:
        await route()
    assert caught.value.status_code == 504
    assert caught.value.detail["code"] == "backend_timeout"
    assert time.perf_counter() - started < .4
    assert environment.records[-1]["error_code"] == "backend_timeout"
    environment.upstream_delay = 0
    assert (await route()).recorded


@pytest.mark.anyio
@pytest.mark.parametrize("audit_delay,audit_status", [(1, 200), (0, 503)])
async def test_audit_failure_keeps_successful_inference(environment, audit_delay, audit_status):
    environment.audit_delay = audit_delay
    environment.audit_status = audit_status
    started = time.perf_counter()
    result = await route()
    assert result.output == "OK" and not result.recorded and result.request_id is None
    assert time.perf_counter() - started < .3
    assert not main.app.state.audit_tasks
    environment.audit_delay = 0
    environment.audit_status = 200
    assert (await route()).recorded


@pytest.mark.anyio
async def test_total_deadline_bounds_multiple_stages(environment, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: settings(request_timeout_seconds=.13, audit_timeout_seconds=.02, upstream_timeout_seconds=.3))
    environment.control_delay = .04
    environment.upstream_delay = .08
    with pytest.raises(HTTPException) as caught:
        await route()
    assert caught.value.detail["code"] == "request_timeout"
    assert environment.records[-1]["status"] == "error"


@pytest.mark.anyio
async def test_control_timeout_never_calls_backend(environment, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: settings(control_timeout_seconds=.01))
    environment.control_delay = .1
    with pytest.raises(HTTPException) as caught:
        await route()
    assert caught.value.detail["code"] == "control_plane_timeout"
    assert not environment.entered.is_set() and not environment.records


@pytest.mark.anyio
async def test_execution_cancellation_finishes_bounded_audit(environment):
    environment.upstream_delay = 1
    task = asyncio.create_task(route())
    await environment.entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert environment.records[-1]["error_code"] == "request_cancelled"
    environment.upstream_delay = 0
    assert (await route()).output == "OK"


@pytest.mark.anyio
async def test_cancellation_during_audit_does_not_drop_record(environment):
    environment.audit_delay = .02
    task = asyncio.create_task(route())
    await environment.audit_entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(environment.records) == 1 and environment.records[0]["status"] == "success"
    assert not main.app.state.audit_tasks


class DripStream(httpx.AsyncByteStream):
    def __init__(self):
        self.closed = False

    async def __aiter__(self):
        while True:
            await asyncio.sleep(.01)
            yield b'data: {"choices":[{"delta":{"content":"x"}}]}\n\n'

    async def aclose(self):
        self.closed = True


@pytest.mark.anyio
async def test_stream_keeps_sending_but_still_hits_absolute_deadline(environment, monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: settings(stream_openai=True, upstream_timeout_seconds=.05))
    environment.stream = DripStream()
    with pytest.raises(HTTPException) as caught:
        await route()
    assert caught.value.detail["code"] == "backend_timeout"
    assert environment.stream.closed
    assert not main.app.state.ttft.samples


@pytest.mark.anyio
async def test_shared_client_does_not_share_user_keys(environment):
    await route("first")
    await route("second")
    assert environment.control_keys == ["first"] * 3 + ["second"] * 3


@pytest.mark.anyio
async def test_lifespan_reuses_and_closes_connection_pools(monkeypatch):
    monkeypatch.setattr(main.app.state, "audit_tasks", set())
    async with main.lifespan(main.app):
        async with main._http_client("http_client") as first:
            async with main._http_client("http_client") as second:
                assert first is second and not first.is_closed
        assert not first.is_closed
    assert first.is_closed and getattr(main.app.state, "http_client", None) is None


@pytest.mark.parametrize("values", [
    {"request_timeout_seconds": 0}, {"audit_timeout_seconds": -1},
    {"upstream_timeout_seconds": float("inf")}, {"control_timeout_seconds": float("nan")},
    {"request_timeout_seconds": 1, "audit_timeout_seconds": 1},
])
def test_invalid_budgets(values):
    with pytest.raises(ValidationError):
        Settings(**values)
