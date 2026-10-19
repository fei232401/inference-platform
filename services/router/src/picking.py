from __future__ import annotations

import random
from typing import Any

POLICIES = frozenset({"weighted_random", "least_latency", "least_inflight", "prefix_affinity"})
RESERVATION_POLICIES = frozenset({"least_inflight", "prefix_affinity"})


def normalize(url: str) -> str:
    return url.rstrip("/")


def pick(ranked: list[dict[str, Any]], policy: str) -> dict[str, Any] | None:
    if policy not in POLICIES:
        raise ValueError("unsupported routing policy")
    if policy in RESERVATION_POLICIES:
        raise ValueError(f"{policy} requires an atomic admission reservation")
    eligible = [item for item in ranked if not item.get("excluded")]
    if not eligible:
        return None
    if policy != "weighted_random":
        return eligible[0]
    total = sum(float(item.get("score") or 0.0) for item in eligible)
    if total <= 0:
        return eligible[0]
    cursor = random.random() * total
    running = 0.0
    for item in eligible:
        running += float(item.get("score") or 0.0)
        if cursor <= running:
            return item
    return eligible[-1]
