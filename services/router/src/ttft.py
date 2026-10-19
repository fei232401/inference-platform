from collections import deque
from datetime import datetime, timezone
import math
import time


class TTFTWindow:
    def __init__(self, max_samples=10000):
        self.samples = deque(maxlen=max_samples)

    def observe(self, model, milliseconds):
        if not math.isfinite(milliseconds) or milliseconds < 0:
            raise ValueError("invalid TTFT")
        self.samples.append((time.time(), model, milliseconds))

    def snapshot(self, model, seconds, now=None):
        now = time.time() if now is None else now
        rows = [row for row in self.samples if row[1] == model and now - seconds <= row[0] <= now]
        values = sorted(row[2] for row in rows)
        return {
            "ttft_p95_ms": math.ceil(values[math.ceil(len(values) * .95) - 1]) if values else 0,
            "sample_count": len(values),
            "observed_at": datetime.fromtimestamp(max(row[0] for row in rows), timezone.utc).isoformat() if rows else None,
            "model": model,
            "window_seconds": seconds,
            "scope": "router_process",
        }
