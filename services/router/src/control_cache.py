from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from typing import Any


class ControlPlaneUnavailable(Exception):
    def __init__(self, original: BaseException) -> None:
        super().__init__(str(original))
        self.original = original


@dataclass
class _Entry:
    value: Any
    stored_at: float


class ControlCache:
    def __init__(self, max_entries: int = 1024, clock: Callable[[], float] = time.monotonic) -> None:
        self._entries: OrderedDict[Hashable, _Entry] = OrderedDict()
        self._inflight: dict[Hashable, asyncio.Future] = {}
        self._max_entries = max_entries
        self._clock = clock

    def __len__(self) -> int:
        return len(self._entries)

    def evict(self, predicate: Callable[[Hashable], bool]) -> None:
        for key in [key for key in self._entries if predicate(key)]:
            del self._entries[key]

    async def get(
        self,
        key: Hashable,
        loader: Callable[[], Awaitable[Any]],
        fresh_seconds: float,
        stale_seconds: float,
    ) -> tuple[Any, str]:
        entry = self._entries.get(key)
        now = self._clock()
        if entry is not None and fresh_seconds > 0 and now - entry.stored_at < fresh_seconds:
            self._entries.move_to_end(key)
            return entry.value, "cached"
        try:
            return await self._load(key, loader), "fresh"
        except ControlPlaneUnavailable:
            entry = self._entries.get(key)
            if entry is not None and stale_seconds > 0 and self._clock() - entry.stored_at <= stale_seconds:
                return entry.value, "stale"
            raise

    async def _load(self, key: Hashable, loader: Callable[[], Awaitable[Any]]) -> Any:
        while (pending := self._inflight.get(key)) is not None:
            try:
                return await asyncio.shield(pending)
            except asyncio.CancelledError:
                if not pending.cancelled():
                    raise
        future = asyncio.get_running_loop().create_future()
        self._inflight[key] = future
        try:
            value = await loader()
        except asyncio.CancelledError:
            future.cancel()
            raise
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()
            raise
        else:
            self._store(key, value)
            future.set_result(value)
            return value
        finally:
            self._inflight.pop(key, None)

    def _store(self, key: Hashable, value: Any) -> None:
        self._entries[key] = _Entry(value, self._clock())
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
