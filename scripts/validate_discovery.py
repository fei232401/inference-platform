import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import urllib.request

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ops.discovery import Discovery  # noqa: E402

NAMESPACE = "ew-validation"
NAME = "discovery"


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


class Run:
    def __init__(self, kubeconfig, test_dsn, retire):
        self.service = "discovery-" + secrets.token_hex(3)
        self.model = self.service + "-model"
        self.kubectl_base = ["kubectl", "--kubeconfig", str(kubeconfig), "--context", "kind-ew-recovery-lab"]
        self.test_dsn, self.retire = test_dsn, retire
        self.state = ROOT / ".state/discovery-e2e"
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.children = []
        self.report = {"started_at": datetime.now(timezone.utc).isoformat(), "steps": [], "status": "running",
                       "conditions": {"retire_seconds": retire, "api": "separate uvicorn on the isolated test database",
                                      "cluster": "Kind single node", "workloads": "busybox placeholders; inference has no readiness probe"}}
        self.t0 = time.time()

    def kubectl(self, *args, body=None, check=True):
        result = subprocess.run(self.kubectl_base + ["-n", NAMESPACE] + list(args), input=body, text=True, capture_output=True, timeout=120)
        if check and result.returncode:
            raise RuntimeError(f"{' '.join(args)}: {result.stderr[-800:]}")
        return result.stdout

    def spawn(self, command, cwd=None, env=None):
        log = open(self.state / f"{Path(command[0]).name}-{len(self.children)}.log", "w")
        child = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
        self.children.append(child)
        return child

    def wait(self, label, predicate, timeout=180, interval=1.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            value = predicate()
            if value:
                return value
            time.sleep(interval)
        raise TimeoutError(label)

    def record(self, name, **evidence):
        entry = {"name": name, "t": round(time.time() - self.t0, 1), **evidence}
        self.report["steps"].append(entry)
        print("STEP", json.dumps(entry, ensure_ascii=False)[:400], flush=True)
        self.save()

    def save(self):
        out = ROOT / "artifacts/discovery-validation.json"
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(self.report, ensure_ascii=False, indent=2) + "\n")

    async def install_key(self, token, pepper):
        import asyncpg
        connection = await asyncpg.connect(self.test_dsn.replace("postgresql+asyncpg://", "postgresql://"))
        try:
            digest = hashlib.sha256((pepper + token).encode()).hexdigest()
            await connection.execute(
                "INSERT INTO api_key(key_prefix,key_hash,name,scopes) VALUES($1,$2,'discovery-e2e',ARRAY['admin','infer']) ON CONFLICT(key_hash) DO NOTHING",
                token[:8], digest)
        finally:
            await connection.close()

    def start_api(self):
        pepper = "discovery-e2e-" + secrets.token_hex(8)
        self.token = "aip_" + secrets.token_urlsafe(24)
        asyncio.run(self.install_key(self.token, pepper))
        port = free_port()
        env = dict(os.environ, DATABASE_DSN=self.test_dsn, AUTH_REQUIRED="true", SECRET_PEPPER=pepper, BACKEND_HEALTH_TTL_SECONDS="0")
        self.spawn([sys.executable, "-m", "uvicorn", "src.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT / "services/api", env=env)
        self.api = f"http://127.0.0.1:{port}"

        def ready():
            try:
                with urllib.request.urlopen(self.api + "/readyz", timeout=2) as response:
                    return response.status == 200
            except OSError:
                return False
        self.wait("api ready", ready, 60)

    def start_proxies(self):
        kube_port, mock_port = free_port(), free_port()
        self.spawn(self.kubectl_base + ["proxy", f"--port={kube_port}"])
        self.spawn(self.kubectl_base + ["-n", NAMESPACE, "port-forward", "deployment/mockrouter", f"{mock_port}:8080"])
        self.kube_api, self.mock = f"http://127.0.0.1:{kube_port}", f"http://127.0.0.1:{mock_port}"

        def up(url):
            def check():
                try:
                    with urllib.request.urlopen(url, timeout=2):
                        return True
                except OSError:
                    return False
            return check
        self.wait("kubectl proxy", up(self.kube_api + "/version"), 30)
        self.wait("mockrouter", up(self.mock + "/ttft_p95"), 30)

    def ttft(self, value):
        with urllib.request.urlopen(f"{self.mock}/control?ttft={value}&samples=100&freeze=0", timeout=5) as response:
            response.read()

    def backends(self):
        with httpx.Client(base_url=self.api, headers={"X-API-Key": self.token}, timeout=5, trust_env=False) as client:
            rows = client.get("/api/v1/backends", params={"limit": 200, "name_like": f"k8s:{NAMESPACE}/{self.service}/"}).raise_for_status().json()["items"]
            candidates = client.get("/api/v1/routing/candidates", params={"model_name": self.model, "policy": "least_inflight"})
        ranked = candidates.json().get("ranked", []) if candidates.status_code == 200 else []
        return {row["name"].rsplit("/", 1)[-1]: row["state"] for row in rows}, sorted(item["name"].rsplit("/", 1)[-1] for item in ranked)

    def pods(self):
        data = json.loads(self.kubectl("get", "pods", "-l", f"elasticworkload.aiinfra.example.com/name={NAME},elasticworkload.aiinfra.example.com/workload=inference", "-o", "json"))
        return {p["metadata"]["name"]: ("Terminating" if p["metadata"].get("deletionTimestamp") else p["status"].get("phase")) for p in data["items"]}

    def sync_until(self, label, predicate, timeout=180):
        def step():
            self.discovery.cycle()
            states, ranked = self.backends()
            return (states, ranked) if predicate(states, ranked) else None
        return self.wait(label, step, timeout, interval=2.0)

    def workload(self):
        resources = {"requests": {"cpu": "50m", "memory": "32Mi"}, "limits": {"cpu": "100m", "memory": "64Mi"}}
        return {
            "apiVersion": "aiinfra.example.com/v1alpha1", "kind": "ElasticWorkload",
            "metadata": {"name": NAME, "namespace": NAMESPACE},
            "spec": {
                "training": {"replicas": 2, "minReplicas": 1, "maxReplicas": 2, "gpuPerWorker": 0, "image": "busybox:1.36",
                             "command": ["sleep", "36000"], "resources": resources},
                "inference": {"replicas": 1, "minReplicas": 1, "maxReplicas": 2, "gpuPerInstance": 0, "image": "busybox:1.36",
                              "command": ["sleep", "36000"], "resources": resources},
                "scalingPolicy": {"targetMetric": "ttft_p95", "slo": 300, "minHoldDuration": 1, "maxScaleStep": 1},
            },
        }

    def service_manifest(self):
        return {"apiVersion": "v1", "kind": "Service", "metadata": {"name": self.service, "namespace": NAMESPACE,
                                                       "labels": {"app.kubernetes.io/part-of": "discovery-e2e"}},
                "spec": {"selector": {"elasticworkload.aiinfra.example.com/name": NAME, "elasticworkload.aiinfra.example.com/workload": "inference"},
                         "ports": [{"name": "http", "port": 8000, "targetPort": 8000}]}}

    def run(self):
        try:
            self.kubectl("delete", "elasticworkloads", NAME, "--ignore-not-found", "--wait=true", check=False)
            self.kubectl("delete", "service", "-l", "app.kubernetes.io/part-of=discovery-e2e", "--ignore-not-found", check=False)
            self.start_api()
            self.record("api_started", service=self.service, model=self.model)
            self.start_proxies()
            self.record("proxies_started")
            self.ttft(210)
            self.kubectl("apply", "-f", "-", body=json.dumps(self.service_manifest()))
            self.kubectl("apply", "-f", "-", body=json.dumps(self.workload()))
            self.discovery = Discovery(self.api, self.token, self.kube_api, NAMESPACE, self.service, self.model,
                                       self.state / "discovery", port_name="http", retire_seconds=self.retire)
            states, ranked = self.sync_until("first pod registered", lambda s, r: list(s.values()) == ["active"])
            self.record("initial_registered", backends=states, candidates=ranked, pods=self.pods())

            started = time.time()
            self.ttft(600)
            states, ranked = self.sync_until("scale-out registered", lambda s, r: sorted(s.values()) == ["active", "active"] and len(r) == 2)
            self.record("scale_out_registered", seconds=round(time.time() - started, 1), backends=states, candidates=ranked, pods=self.pods())
            self.ttft(210)

            started = time.time()
            self.ttft(120)
            states, ranked = self.sync_until("scale-in drained", lambda s, r: sorted(s.values()) == ["active", "draining"] and len(r) == 1)
            self.record("scale_in_drained", seconds=round(time.time() - started, 1), backends=states, candidates=ranked, pods=self.pods())
            states, ranked = self.sync_until("drained backend retired", lambda s, r: sorted(s.values()) == ["active", "disabled"], timeout=240)
            self.record("scale_in_retired", seconds=round(time.time() - started, 1), backends=states, candidates=ranked, pods=self.pods())
            self.ttft(210)

            survivor = next(name for name, phase in self.pods().items() if phase == "Running")
            started = time.time()
            self.kubectl("delete", "pod", survivor, "--wait=false")
            states, ranked = self.sync_until("replacement registered",
                                             lambda s, r: s.get(survivor) in {"draining", "disabled"} and len(r) == 1 and r[0] != survivor)
            self.record("pod_replaced", seconds=round(time.time() - started, 1), deleted=survivor, backends=states, candidates=ranked, pods=self.pods())
            events = (self.state / "discovery/discovery-events.jsonl").read_text().splitlines()
            self.record("event_log", actions=[json.loads(line)["action"] for line in events])
            self.report["status"] = "passed"
        except Exception as exc:
            self.report["status"] = "failed"
            self.report["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.report["finished_at"] = datetime.now(timezone.utc).isoformat()
            self.save()
            self.kubectl("delete", "elasticworkloads", NAME, "--ignore-not-found", "--wait=false", check=False)
            self.kubectl("delete", "service", self.service, "--ignore-not-found", check=False)
            for child in self.children:
                child.terminate()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", type=Path, required=True)
    parser.add_argument("--test-dsn", required=True, help="isolated database whose name ends with _test")
    parser.add_argument("--retire-seconds", type=float, default=15)
    args = parser.parse_args()
    if not args.test_dsn.rsplit("/", 1)[-1].endswith("_test"):
        parser.error("refusing to write to a database whose name does not end with _test")
    Run(args.kubeconfig, args.test_dsn, args.retire_seconds).run()
