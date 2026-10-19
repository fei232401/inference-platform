import json
from pathlib import Path
import subprocess
import time
import uuid

import httpx


ROOT = Path(__file__).resolve().parents[1]
OLLAMA = "http://127.0.0.1:18107"
BRIDGE = "http://172.19.0.1:18107"
API = "http://127.0.0.1:18000"
ROUTER = "http://127.0.0.1:18001"


def main():
    suffix = uuid.uuid4().hex[:10]
    profile = "fei-cpu-validation-" + suffix
    report = {"scope": "independent CPU Ollama and GPU vLLM requests; different model sizes", "checks": {}, "status": "running"}
    folder = ROOT / "artifacts/local-engines"
    folder.mkdir(parents=True, exist_ok=True)
    process = None
    gpu_binding = None
    cpu_backend = None
    created_profile = False
    with httpx.Client(timeout=60, trust_env=False) as engine, httpx.Client(timeout=60, trust_env=False, headers={
        "X-API-Key": (ROOT / ".state/admin-key").read_text().strip(),
    }) as client:
        def check(name, passed, evidence=None):
            report["checks"][name] = {"passed": bool(passed), "evidence": evidence}
            if not passed:
                raise AssertionError(name)
            print("PASS", name, flush=True)

        def call(method, path, **kwargs):
            response = client.request(method, API + path, **kwargs)
            response.raise_for_status()
            return response.json()

        try:
            for _ in range(30):
                try:
                    client.get(ROUTER + "/readyz", timeout=2).raise_for_status()
                    break
                except httpx.HTTPError:
                    time.sleep(.3)
            else:
                raise RuntimeError("Router is not ready")
            try:
                engine.get(OLLAMA + "/api/version", timeout=2).raise_for_status()
            except httpx.HTTPError:
                with (folder / "forward.log").open("w") as output:
                    process = subprocess.Popen([
                        "kubectl", "--context", "k3d-ai-cluster", "--server=https://127.0.0.1:46121", "-n", "ai-platform",
                        "port-forward", "--address=127.0.0.1,172.19.0.1", "service/ollama-service", "18107:11434",
                    ], stdout=output, stderr=subprocess.STDOUT)
                for _ in range(30):
                    try:
                        engine.get(OLLAMA + "/api/version", timeout=1).raise_for_status()
                        break
                    except httpx.HTTPError:
                        time.sleep(.3)
                else:
                    raise RuntimeError("Ollama forwarding unavailable")
            models = engine.get(OLLAMA + "/api/tags").raise_for_status().json()["models"]
            check("existing_model_no_download", any(row["name"] == "qwen2.5:1.5b" for row in models))
            response = engine.post(OLLAMA + "/api/create", json={
                "model": profile, "from": "qwen2.5:1.5b", "stream": False,
                "parameters": {"num_gpu": 0, "num_ctx": 512, "temperature": 0},
            })
            response.raise_for_status()
            created_profile = True
            check("cpu_profile_created", response.json().get("status") == "success")
            backends = call("GET", "/api/v1/backends", params={"limit": 200})["items"]
            gpu = next(row for row in backends if row["name"] == "vllm-demo" and row["state"] == "active" and row["engine"] == "openai")
            cpu = next((row for row in backends if row["url"].rstrip("/") == BRIDGE), None)
            if cpu is not None and (not cpu["name"].startswith("cpu-validation-") or cpu["state"] != "disabled"):
                raise RuntimeError("The validation URL belongs to an active or unrelated backend")
            bindings = []
            for label, backend, engine_model in [("gpu", gpu, "/models/qwen2.5-3b-awq"), ("cpu", cpu, profile)]:
                model = call("POST", "/api/v1/models/upsert", json={"name": f"hetero-{label}-{suffix}"})
                if label == "gpu":
                    call("POST", f'/api/v1/backends/{gpu["id"]}/models', json={"model_ids": [model["id"]]})
                    gpu_binding = (gpu["id"], model["id"])
                elif backend is None:
                    backend = call("POST", "/api/v1/backends", json={"name": "cpu-validation-" + suffix, "url": BRIDGE,
                        "engine": "ollama", "model_ids": [model["id"]]})
                    cpu_backend = backend["id"]
                else:
                    cpu_backend = backend["id"]
                    call("POST", f'/api/v1/backends/{cpu_backend}/models', json={"model_ids": [model["id"]]})
                    call("POST", f'/api/v1/backends/{cpu_backend}/state', json={"state": "active"})
                if label == "cpu":
                    call("POST", f'/api/v1/backends/{backend["id"]}/health', json={"healthy": True})
                bindings.append({"label": label, "backend": backend, "model": model, "engine_model": engine_model})
            for binding in bindings:
                backend = binding["backend"]
                response = client.post(ROUTER + "/v1/route", json={
                    "model_name": binding["model"]["name"], "prompt": "Reply only OK.", "max_tokens": 4,
                    "policy": "least_inflight", "engine_models": {backend["name"]: binding["engine_model"]},
                })
                response.raise_for_status()
                data = response.json()
                stored = call("GET", "/api/v1/requests/" + data["request_id"])
                check(binding["label"] + "_router_generation_and_audit",
                      bool(data["output"].strip()) and data["recorded"] and data["backend"]["id"] == backend["id"] and stored["status"] == "success" and stored["backend_id"] == backend["id"],
                      {"request_id": data["request_id"], "output": data["output"], "engine": data["backend"]["engine"], "model": binding["engine_model"], "timings": data["timings"]})
            running = engine.get(OLLAMA + "/api/ps").raise_for_status().json()["models"]
            row = next(item for item in running if item["name"].split(":")[0] == profile)
            check("ollama_cpu_placement", row.get("size_vram") == 0 and row.get("size", 0) > 0, row)
            response = engine.get("http://127.0.0.1:18104/health")
            check("gpu_engine_remains_healthy", response.status_code == 200)
            report["status"] = "passed"
        except Exception as exc:
            report["status"] = "failed"
            report["error"] = str(exc)
            raise
        finally:
            errors = []
            if cpu_backend:
                try: call("DELETE", f"/api/v1/backends/{cpu_backend}")
                except Exception as exc: errors.append(str(exc))
            if gpu_binding:
                try: call("DELETE", f"/api/v1/backends/{gpu_binding[0]}/models", json={"model_ids": [gpu_binding[1]]})
                except Exception as exc: errors.append(str(exc))
            if created_profile:
                try:
                    engine.post(OLLAMA + "/api/generate", json={"model": profile, "keep_alive": 0}).raise_for_status()
                    engine.request("DELETE", OLLAMA + "/api/delete", json={"model": profile}).raise_for_status()
                except Exception as exc: errors.append(str(exc))
            if process is not None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired: process.kill()
            report["cleanup_errors"] = errors
            if errors: report["status"] = "failed"
            (folder / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps({"status": report["status"], "report": str(folder / "report.json"), "cleanup_errors": errors}), flush=True)
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
