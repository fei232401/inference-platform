from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time

import httpx


def transition(previous, healthy, failures=3, successes=2):
    state = dict(previous or {"healthy": None, "failures": 0, "successes": 0})
    state["failures"] = 0 if healthy else min(failures, state["failures"] + 1)
    state["successes"] = min(successes, state["successes"] + 1) if healthy else 0
    if state["failures"] >= failures:
        state["healthy"] = False
    elif state["successes"] >= successes:
        state["healthy"] = True
    return state


class Monitor:
    def __init__(self, api, key, folder, timeout=2, failures=3, successes=2):
        self.api, self.key = api.rstrip("/"), key
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.timeout, self.failures, self.successes = timeout, failures, successes
        path = self.folder / "probe-state.json"
        self.states = json.loads(path.read_text()) if path.exists() else {}

    def probe(self, backend):
        started = time.monotonic()
        path = "/api/tags" if backend["engine"] == "ollama" else "/health"
        try:
            response = httpx.get(backend["url"].rstrip("/") + path, timeout=self.timeout, follow_redirects=False)
            return response.status_code == 200, int((time.monotonic() - started) * 1000)
        except httpx.RequestError:
            return False, None

    def cycle(self):
        headers = {"X-API-Key": self.key}
        with httpx.Client(base_url=self.api, headers=headers, timeout=5) as client:
            backends, offset = [], 0
            while True:
                page = client.get("/api/v1/backends", params={"limit": 200, "offset": offset}).raise_for_status().json()
                backends.extend(row for row in page["items"] if row["state"] == "active")
                if not page["meta"]["has_more"]:
                    break
                offset += len(page["items"])
            with ThreadPoolExecutor(max_workers=8) as executor:
                observations = list(executor.map(self.probe, backends))
            for backend, (healthy, latency) in zip(backends, observations):
                key = str(backend["id"])
                previous = self.states.get(key)
                state = transition(previous, healthy, self.failures, self.successes)
                if state["healthy"] is not None:
                    client.post(f'/api/v1/backends/{key}/health', json={"healthy": state["healthy"], "latency_ms": latency, "error": None if healthy else "health_probe_failed"}).raise_for_status()
                if (previous or {}).get("healthy") != state["healthy"]:
                    with (self.folder / "probe-events.jsonl").open("a") as output:
                        output.write(json.dumps({"at": time.time(), "backend_id": backend["id"], "healthy": state["healthy"]}) + "\n")
                self.states[key] = state
            live = {str(row["id"]) for row in backends}
            self.states = {key: value for key, value in self.states.items() if key in live}
            temporary = self.folder / "probe-state.tmp"
            temporary.write_text(json.dumps(self.states))
            temporary.replace(self.folder / "probe-state.json")
            (self.folder / "heartbeat").write_text(str(time.time()))
        return len(backends)


def main():
    key = Path(os.environ["ADMIN_KEY_FILE"]).read_text().strip()
    monitor = Monitor(os.getenv("CONTROL_PLANE_URL", "http://api:8000"), key, os.getenv("PROBE_STATE_DIR", "/state"))
    while True:
        try:
            count = monitor.cycle()
            print(json.dumps({"event": "probe_cycle", "backends": count, "at": time.time()}), flush=True)
        except Exception as exc:
            print(json.dumps({"event": "probe_cycle_failed", "error_type": type(exc).__name__}), flush=True)
        time.sleep(float(os.getenv("PROBE_INTERVAL_SECONDS", "15")))


if __name__ == "__main__":
    main()
