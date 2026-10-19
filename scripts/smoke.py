import asyncio
from contextlib import suppress
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import time
import uuid
import tempfile

import asyncpg
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ops.health import Monitor
ARTIFACTS = ROOT / "artifacts"
environment = dict(os.environ)
private_libs = ROOT / ".state/browser-libs/usr/lib/x86_64-linux-gnu"
if private_libs.exists():
    environment["LD_LIBRARY_PATH"] = str(private_libs) + ":" + environment.get("LD_LIBRARY_PATH", "")
environment.setdefault("SECRET_PEPPER", "isolated-smoke-pepper")
environment["AUTH_REQUIRED"] = "true"
environment["CONTROL_PLANE_URL"] = "http://127.0.0.1:18100"
environment["VITE_DEV_API_TARGET"] = environment["CONTROL_PLANE_URL"]
environment["VITE_DEV_ROUTER_TARGET"] = "http://127.0.0.1:18101"
environment["BROWSER_BASE_URL"] = "http://127.0.0.1:15173"
environment["DATABASE_DSN"] = environment["TEST_DATABASE_DSN"]
engine = environment.get("ENGINE_URL", "http://127.0.0.1:18102")
processes = []
handles = []
checks = []


def launch(name, args, cwd):
    handle = (ARTIFACTS / f"{name}.log").open("w")
    handles.append(handle)
    process = subprocess.Popen(args, cwd=cwd, env=environment, stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    processes.append(process)
    return process


def wait(url):
    for _ in range(100):
        try:
            response = httpx.get(url, timeout=1)
            if response.status_code == 200:
                return
        except httpx.RequestError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"Not ready: {url}")


def expect(response, code, name):
    if response.status_code != code:
        raise RuntimeError(f"{name}: expected {code}, got {response.status_code}: {response.text[:200]}")
    checks.append(name)
    return response.json()


async def schema_version(value):
    connection = await asyncpg.connect(environment["DATABASE_DSN"].replace("postgresql+asyncpg://", "postgresql://"))
    try:
        await connection.execute("UPDATE schema_migration SET version=$1", value)
    finally:
        await connection.close()


def main():
    ARTIFACTS.mkdir(exist_ok=True)
    if not environment["DATABASE_DSN"].split("?")[0].endswith("_test"):
        raise RuntimeError("Smoke requires an isolated _test database")
    subprocess.run([sys.executable, str(ROOT / "scripts/bootstrap.py")], env=environment, check=True)
    if "ENGINE_URL" not in environment:
        marker = ROOT / ".state/mock-health"
        marker.write_text("ok")
        environment["MOCK_ENGINE_HEALTH_FILE"] = str(marker)
        launch("mock-engine", [sys.executable, str(ROOT / "scripts/mock_engine.py")], ROOT)
    for service, port in [("api", "18100"), ("router", "18101")]:
        launch(service, [sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", port], ROOT / "services" / service)
        wait(f"http://127.0.0.1:{port}/readyz")
    launch("web", ["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "15173"], ROOT / "web")
    wait(environment["BROWSER_BASE_URL"])
    token = (ROOT / ".state/admin-key").read_text().strip()
    headers = {"X-API-Key": token}
    api = environment["CONTROL_PLANE_URL"]
    router = environment["VITE_DEV_ROUTER_TARGET"]
    suffix = uuid.uuid4().hex[:10]
    model = "smoke-" + suffix
    backend = "engine-" + suffix
    with httpx.Client(timeout=60, headers=headers) as client:
        expect(httpx.get(api + "/api/v1/backends"), 401, "missing_key")
        expect(httpx.get(api + "/api/v1/backends", headers={"X-API-Key": "invalid"}), 401, "forged_key")
        m = expect(client.post(api + "/api/v1/models", json={"name": model}), 201, "register_model")
        registered = client.get(api + "/api/v1/backends", params={"limit": 200}).raise_for_status().json()["items"]
        b = next((row for row in registered if row["url"].rstrip("/") == engine.rstrip("/")), None)
        if b is None:
            b = expect(client.post(api + "/api/v1/backends", json={"name": backend, "url": engine, "engine": "openai", "model_ids": [m["id"]]}), 201, "register_backend")
        else:
            backend = b["name"]
            expect(client.post(api + f'/api/v1/backends/{b["id"]}/models', json={"model_ids": [m["id"]]}), 200, "bind_model_to_existing_backend")
            if b["state"] != "active":
                expect(client.post(api + f'/api/v1/backends/{b["id"]}/state', json={"state": "active"}), 200, "activate_existing_backend")
        engine_model = model
        if "ENGINE_URL" in environment:
            engine_model = client.get(engine + "/v1/models").raise_for_status().json()["data"][0]["id"]
        payload = {"model_name": model, "prompt": "只回复你好", "policy": "least_latency", "max_tokens": 16, "engine_models": {backend: engine_model}}
        result = expect(client.post(router + "/v1/route", json=payload), 200, "generate_and_record")
        assert result["output"].strip() and result["recorded"] and result["request_id"]
        detail = expect(client.get(api + "/api/v1/requests/" + result["request_id"]), 200, "read_persisted_request")
        assert detail["status"] == "success" and detail["backend_id"] == b["id"]
        checks.append("output_and_database_match")
        missing = dict(payload, model_name="missing-" + suffix)
        expect(client.post(router + "/v1/route", json=missing), 503, "no_candidates")
        expect(client.post(api + f'/api/v1/backends/{b["id"]}/state', json={"state": "disabled"}), 200, "disable_backend")
        expect(client.post(router + "/v1/route", json=payload), 503, "disabled_backend_not_routed")
        expect(client.post(api + f'/api/v1/backends/{b["id"]}/state', json={"state": "active"}), 200, "restore_backend")
        if "ENGINE_URL" not in environment:
            expect(client.post(router + "/v1/route", json=dict(payload, prompt="__fail__")), 502, "upstream_failure")
        if "ENGINE_URL" not in environment:
            with tempfile.TemporaryDirectory(prefix="health-check-") as folder:
                monitor = Monitor(api, token, folder)
                monitor.cycle()
                monitor.cycle()
                marker.write_text("fail")
                for _ in range(3):
                    monitor.cycle()
                expect(client.post(router + "/v1/route", json=payload), 503, "probe_failure_excludes_backend")
                marker.write_text("ok")
                monitor.cycle()
                expect(client.post(router + "/v1/route", json=payload), 503, "single_success_does_not_reenable")
                monitor.cycle()
                expect(client.post(router + "/v1/route", json=payload), 200, "probe_recovery_restores_routing")
                events = [json.loads(line) for line in (Path(folder) / "probe-events.jsonl").read_text().splitlines()]
                backend_events = [event for event in events if event["backend_id"] == b["id"]]
                assert [event["healthy"] for event in backend_events] == [True, False, True]
                checks.append("health_events_deduplicated")
        key = expect(client.post(api + "/api/v1/keys", json={"name": "temporary-" + suffix, "scopes": ["infer"]}), 201, "create_scoped_key")
        expect(client.post(api + f'/api/v1/keys/{key["id"]}/revoke'), 200, "revoke_key")
        expect(httpx.post(router + "/v1/route", json=payload, headers={"X-API-Key": key["key"]}), 401, "revoked_key_rejected")
        asyncio.run(schema_version(999))
        try:
            expect(client.get(api + "/readyz"), 503, "schema_mismatch_api")
            expect(client.get(router + "/readyz"), 503, "schema_mismatch_router")
        finally:
            asyncio.run(schema_version(1))
        if os.getenv("SKIP_BROWSER") != "1":
            environment["BROWSER_MODEL"] = model
            environment["BROWSER_ENGINE_MODEL"] = engine_model
            environment["BROWSER_BACKEND"] = backend
            subprocess.run(["npx", "playwright", "test"], cwd=ROOT / "web", env=environment, check=True)
            checks.append("browser_inference_and_persistence")
        report = {"engine": "real_vllm" if "ENGINE_URL" in environment else "mock_openai", "checks": checks, "request_id": result["request_id"], "output": result["output"], "total_ms": result["timings"]["total_ms"]}
        (ARTIFACTS / (report["engine"] + "-smoke.json")).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    finally:
        for process in reversed(processes):
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
        for process in reversed(processes):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        for handle in handles:
            handle.close()
