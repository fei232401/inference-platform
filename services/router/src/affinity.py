from __future__ import annotations

import hashlib
import math
from typing import Any


def affinity_key(prompt: str, prefix_chars: int) -> str:
    return hashlib.sha256(prompt[:prefix_chars].encode()).hexdigest()


def rendezvous_order(key: str, eligible: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def weight(item: dict[str, Any]) -> int:
        digest = hashlib.sha256(f"{key}|{item['backend_id']}".encode()).digest()
        return int.from_bytes(digest[:8], "big")

    return sorted(eligible, key=lambda item: (-weight(item), int(item["backend_id"])))


def bounded_choice(key: str, eligible: list[dict[str, Any]], load_factor: float) -> tuple[dict[str, Any], dict[str, Any]]:
    total = sum(int(item["inflight"]) for item in eligible)
    bound = max(1, math.ceil(load_factor * (total + 1) / len(eligible)))
    order = rendezvous_order(key, eligible)
    rank, chosen = next((rank, item) for rank, item in enumerate(order) if int(item["inflight"]) < bound)
    return chosen, {"preferred_id": int(order[0]["backend_id"]), "rank": rank, "load_bound": bound}
