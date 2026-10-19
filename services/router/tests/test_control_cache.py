import asyncio

import pytest

from src.control_cache import ControlCache, ControlPlaneUnavailable


@pytest.fixture
def anyio_backend():
    return "asyncio"


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Loader:
    def __init__(self, value="v"):
        self.calls = 0
        self.value = value
        self.error = None
        self.gate = None

    async def __call__(self):
        self.calls += 1
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        return self.value


@pytest.mark.anyio
async def test_fresh_entry_is_reused_until_it_expires():
    clock, loader = Clock(), Loader()
    cache = ControlCache(clock=clock)
    assert await cache.get("k", loader, 2, 30) == ("v", "fresh")
    clock.now = 1.9
    assert await cache.get("k", loader, 2, 30) == ("v", "cached")
    clock.now = 2.0
    assert await cache.get("k", loader, 2, 30) == ("v", "fresh")
    assert loader.calls == 2


@pytest.mark.anyio
async def test_zero_ttl_disables_reuse():
    loader = Loader()
    cache = ControlCache(clock=Clock())
    await cache.get("k", loader, 0, 0)
    await cache.get("k", loader, 0, 0)
    assert loader.calls == 2


@pytest.mark.anyio
async def test_concurrent_misses_share_one_load():
    loader = Loader()
    loader.gate = asyncio.Event()
    cache = ControlCache(clock=Clock())
    tasks = [asyncio.create_task(cache.get("k", loader, 2, 30)) for _ in range(20)]
    await asyncio.sleep(0)
    loader.gate.set()
    results = await asyncio.gather(*tasks)
    assert loader.calls == 1
    assert {value for value, _ in results} == {"v"}


@pytest.mark.anyio
async def test_unavailable_control_plane_serves_bounded_stale_snapshot():
    clock, loader = Clock(), Loader()
    cache = ControlCache(clock=clock)
    await cache.get("k", loader, 2, 30)
    loader.error = ControlPlaneUnavailable(TimeoutError())
    clock.now = 10
    assert await cache.get("k", loader, 2, 30) == ("v", "stale")
    clock.now = 30.1
    with pytest.raises(ControlPlaneUnavailable):
        await cache.get("k", loader, 2, 30)


@pytest.mark.anyio
async def test_authoritative_errors_never_fall_back_to_stale():
    clock, loader = Clock(), Loader()
    cache = ControlCache(clock=clock)
    await cache.get("k", loader, 2, 30)
    loader.error = PermissionError("revoked")
    clock.now = 3
    with pytest.raises(PermissionError):
        await cache.get("k", loader, 2, 30)


@pytest.mark.anyio
async def test_follower_retries_when_leader_is_cancelled():
    loader = Loader()
    loader.gate = asyncio.Event()
    cache = ControlCache(clock=Clock())
    leader = asyncio.create_task(cache.get("k", loader, 2, 30))
    await asyncio.sleep(0)
    follower = asyncio.create_task(cache.get("k", loader, 2, 30))
    await asyncio.sleep(0)
    leader.cancel()
    await asyncio.sleep(0)
    loader.gate.set()
    assert await follower == ("v", "fresh")
    with pytest.raises(asyncio.CancelledError):
        await leader
    assert loader.calls == 2


@pytest.mark.anyio
async def test_entries_are_bounded_and_evictable():
    cache = ControlCache(max_entries=2, clock=Clock())
    for key in ("a", "b", "c"):
        await cache.get((key, "user"), Loader(key), 2, 30)
    assert len(cache) == 2
    cache.evict(lambda key: key[1] == "user")
    assert len(cache) == 0
