import argparse
import importlib.util
from pathlib import Path

import httpx
import pytest


spec = importlib.util.spec_from_file_location("benchmark_gpu", Path(__file__).parents[1] / "scripts/benchmark_gpu.py")
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def settings(mode="direct"):
    return argparse.Namespace(mode=mode, model="test", prompt="test", tokens=8, url="http://test")


def test_percentile_uses_nearest_rank():
    assert benchmark.percentile([], .95) is None
    assert benchmark.percentile([4, 1, 3, 2], .5) == 2
    assert benchmark.percentile([4, 1, 3, 2], .95) == 4


@pytest.mark.asyncio
async def test_direct_waits_for_content_and_reads_real_usage():
    events = '\n\n'.join([
        'data: {"choices":[{"delta":{"role":"assistant","content":""}}]}',
        'data: {"choices":[{"delta":{"content":"hello"}}]}',
        'data: {"choices":[],"usage":{"prompt_tokens":12,"completion_tokens":1}}',
        'data: [DONE]',
    ])
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=events))) as client:
        result = await benchmark.request(client, settings(), 0)
    assert result["success"]
    assert result["ttft_ms"] is not None
    assert result["completion_tokens"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("events", [
    'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n',
    'data: {"choices":[],"usage":{"completion_tokens":1}}\n\ndata: [DONE]\n',
    'data: {"error":{"message":"failure"}}\n',
])
async def test_incomplete_stream_is_failure(events):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text=events))) as client:
        result = await benchmark.request(client, settings(), 0)
    assert not result["success"]


@pytest.mark.asyncio
async def test_router_rejection_keeps_status_without_fake_ttft():
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(429))) as client:
        result = await benchmark.request(client, settings("router"), 0)
    assert not result["success"]
    assert result["http_status"] == 429
    assert result["ttft_ms"] is None
