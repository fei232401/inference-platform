import json
from types import SimpleNamespace

import httpx
import pytest

from src import main
from src.ttft import TTFTWindow


def test_window_uses_nearest_rank_and_scopes_model(monkeypatch):
    monkeypatch.setattr("src.ttft.time.time", lambda: 100)
    window = TTFTWindow()
    for value in range(1, 21):
        window.observe("a", value)
    window.observe("b", 999)
    assert window.snapshot("a", 30, 100)["ttft_p95_ms"] == 19
    assert window.snapshot("a", 30, 100)["sample_count"] == 20
    assert window.snapshot("a", 30, 131)["sample_count"] == 0
    assert window.snapshot("a", 30, 99)["sample_count"] == 0


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_measurement(value):
    with pytest.raises(ValueError):
        TTFTWindow().observe("a", value)


def test_window_is_bounded():
    window = TTFTWindow(2)
    for value in range(3):
        window.observe("a", value)
    assert len(window.samples) == 2


@pytest.mark.anyio
@pytest.mark.parametrize("complete", [True, False])
async def test_stream_content_usage_and_incomplete_rejection(monkeypatch, complete):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(stream_openai=True))
    window = TTFTWindow()
    monkeypatch.setattr(main.app.state, "ttft", window)
    lines = [
        {"choices": [{"delta": {"role": "assistant"}}]},
        {"choices": [{"delta": {"content": "hello"}}]},
        {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 1}},
    ]
    body = "".join("data: " + json.dumps(row) + "\n\n" for row in lines)
    if complete:
        body += "data: [DONE]\n\n"
    def upstream(request):
        assert json.loads(request.content)["stream"]
        return httpx.Response(200, text=body)
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as client:
        if complete:
            assert await main._call_backend(client, "openai", "http://engine", "model", "hi", 1, "alias") == ("hello", 10, 1)
            assert window.snapshot("alias", 30)["sample_count"] == 1
        else:
            with pytest.raises(ValueError, match="incomplete"):
                await main._call_backend(client, "openai", "http://engine", "model", "hi", 1)
            assert len(window.samples) == 0


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_stream_http_failure_keeps_readable_error_body(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(stream_openai=True))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500, text="busy"))) as client:
        with pytest.raises(httpx.HTTPStatusError) as caught:
            await main._call_backend(client, "openai", "http://engine", "model", "hi", 1)
        assert caught.value.response.text == "busy"


@pytest.mark.anyio
@pytest.mark.parametrize("query,expected", [("", "default"), ("?model=other", "other")])
async def test_ttft_endpoint_selects_requested_model(monkeypatch, query, expected):
    monkeypatch.setattr(main, "get_settings", lambda: SimpleNamespace(ttft_model="default", ttft_window_seconds=30))
    window = TTFTWindow()
    window.observe("default", 10)
    window.observe("other", 20)
    monkeypatch.setattr(main.app.state, "ttft", window)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://router") as client:
        response = await client.get("/ttft_p95" + query)
    assert response.status_code == 200
    assert response.json()["model"] == expected
