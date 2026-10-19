from __future__ import annotations

import random
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Any

from .metrics import BACKEND_INFLIGHT
from .picking import pick


class AdmissionRejected(Exception):
    def __init__(self, code: str, ranked: list[dict[str, Any]]) -> None:
        super().__init__(code)
        self.code = code
        self.ranked = ranked


@dataclass(frozen=True)
class Reservation:
    chosen: dict[str, Any]
    ranked: list[dict[str, Any]]


class AdmissionController:
    def __init__(self) -> None:
        self._lock = Lock()
        self._inflight: dict[int, int] = {}

    @contextmanager
    def reserve(
        self,
        ranked: list[dict[str, Any]],
        policy: str,
        default_limit: int,
        limits: dict[str, int],
    ) -> Iterator[Reservation]:
        with self._lock:
            snapshot = []
            healthy = False
            for item in ranked:
                backend_id = int(item["backend_id"])
                inflight = self._inflight.get(backend_id, 0)
                limit = limits.get(str(backend_id), default_limit)
                capacity_excluded = inflight >= limit
                healthy = healthy or not item.get("excluded", False)
                snapshot.append({
                    **item,
                    "excluded": bool(item.get("excluded")) or capacity_excluded,
                    "inflight": inflight,
                    "max_inflight": limit,
                    "capacity_excluded": capacity_excluded,
                    "reasons": [*item.get("reasons", []), *(["capacity_full"] if capacity_excluded else [])],
                })
            eligible = [item for item in snapshot if not item["excluded"]]
            if not eligible:
                raise AdmissionRejected("backend_capacity_exhausted" if healthy else "no_candidate", snapshot)
            if policy == "least_inflight":
                minimum = min(item["inflight"] for item in eligible)
                chosen = random.choice([item for item in eligible if item["inflight"] == minimum])
            else:
                chosen = pick(eligible, policy)
                if chosen is None:
                    raise AdmissionRejected("no_candidate", snapshot)
            backend_id = int(chosen["backend_id"])
            self._inflight[backend_id] = self._inflight.get(backend_id, 0) + 1
            BACKEND_INFLIGHT.labels(backend_id=str(backend_id)).inc()
        try:
            yield Reservation(chosen=chosen, ranked=snapshot)
        finally:
            with self._lock:
                remaining = self._inflight[backend_id] - 1
                if remaining:
                    self._inflight[backend_id] = remaining
                else:
                    del self._inflight[backend_id]
                BACKEND_INFLIGHT.labels(backend_id=str(backend_id)).dec()
