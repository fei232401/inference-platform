import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import subprocess
import time
import uuid

import httpx


ROOT = Path(__file__).resolve().parents[1]
OPERATOR = ROOT.parent / "elastic-workload-operator"
CONTEXT = "kind-ew-recovery-lab"
KUBE = ["kubectl", "--context", CONTEXT, "--kubeconfig", str(OPERATOR / ".state/validation.kubeconfig")]
MODEL = "/models/qwen2.5-3b-awq"


def command(args, **kwargs):
    result = subprocess.run(args, capture_output=True, text=True, timeout=180, **kwargs)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr[-2000:]}")
    return result.stdout


def prepare(folder):
    environment = dict(os.environ, GOTOOLCHAIN="go1.26.9", CGO_ENABLED="0")
    command(["go", "build", "-o", str(folder / "manager"), "./cmd/main.go"], cwd=OPERATOR, env=environment)
    command(["docker", "build", "-t", "ew-operator:closure-v1", "-f", str(OPERATOR / "packaging/Dockerfile.binary"), str(folder)])
    command(["docker", "build", "-t", "inference-platform/router:closure-v1", "-f", "packaging/Dockerfile.router-local", "."], cwd=ROOT)
    command(["docker", "tag", "nginx:alpine", "nginx:ew-closure"])
    archive = folder / "images.tar"
    command(["docker", "save", "--platform", "linux/amd64", "-o", str(archive), "ew-operator:closure-v1", "inference-platform/router:closure-v1", "nginx:alpine", "nginx:ew-closure", "busybox:1.36"])
    command(["docker", "cp", str(archive), "ew-recovery-lab-control-plane:/var/ew-integration-images.tar"])
    try:
        command(["docker", "exec", "ew-recovery-lab-control-plane", "ctr", "-n", "k8s.io", "images", "import", "/var/ew-integration-images.tar"])
    finally:
        command(["docker", "exec", "ew-recovery-lab-control-plane", "rm", "-f", "/var/ew-integration-images.tar"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    folder = ROOT / "artifacts/projects-integration"
    folder.mkdir(parents=True, exist_ok=True)
    namespace = "ew-link-" + uuid.uuid4().hex[:8]
    alias = namespace
    relay = namespace + "-relay"
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "namespace": namespace,
              "scope": "CPU serving proxies sharing one external GPU engine; threshold-controlled actuation", "checks": {}}
    processes = []
    backend_id = None
    paused = False
    relay_started = False
    created_namespace = False
    client = httpx.Client(timeout=60, trust_env=False, headers={"X-API-Key": (ROOT / ".state/admin-key").read_text().strip()})

    def check(name, condition, evidence=None):
        report["checks"][name] = {"passed": bool(condition), "evidence": evidence}
        (folder / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        if not condition:
            raise AssertionError(name)
        print("PASS", name, flush=True)

    def apply(resource):
        command(KUBE + ["apply", "-f", "-"], input=json.dumps(resource))

    def get(resource, name):
        return json.loads(command(KUBE + ["-n", namespace, "get", resource, name, "-o", "json"]))

    def patch(spec):
        command(KUBE + ["-n", namespace, "patch", "elasticworkload", "linked", "--type=merge", "-p", json.dumps({"spec": spec})])

    def degraded():
        obj = get("elasticworkload", "linked")
        return obj.get("status", {}).get("phase") == "Degraded" and any(
            row["type"] == "Ready" and row["reason"] == "InvalidAllocation" for row in obj["status"]["conditions"])

    def template_available(image=None, memory=None):
        dep = get("deployment", "linked-inference")
        container = dep["spec"]["template"]["spec"]["containers"][0]
        return (image is None or container["image"] == image) and (memory is None or container["resources"]["limits"]["memory"] == memory) and dep["status"].get("observedGeneration", 0) >= dep["metadata"]["generation"] and dep["status"].get("updatedReplicas", 0) == dep["spec"]["replicas"] and dep["status"].get("availableReplicas", 0) == dep["spec"]["replicas"] and dep["status"].get("replicas", 0) == dep["spec"]["replicas"]

    def endpoint_count():
        slices = json.loads(command(KUBE + ["-n", namespace, "get", "endpointslices", "-l", "kubernetes.io/service-name=serving", "-o", "json"]))
        return len({address for item in slices["items"] for endpoint in item.get("endpoints", [])
                    if endpoint.get("conditions", {}).get("ready") and not endpoint.get("conditions", {}).get("terminating")
                    for address in endpoint["addresses"]})

    def wait(predicate, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if predicate():
                    return
            except (httpx.HTTPError, RuntimeError, KeyError):
                pass
            time.sleep(1)
        raise TimeoutError("integration condition did not converge")

    def allocation(training, inference):
        obj = get("elasticworkload", "linked")
        return obj.get("status", {}).get("readyReplicas") == {"training": training, "inference": inference} and obj["status"].get("desiredReplicas") == {"training": training, "inference": inference}

    def route(count):
        results = []
        for index in range(count):
            response = client.post("http://127.0.0.1:18201/v1/route", json={
                "model_name": alias, "engine_models": {alias: MODEL},
                "prompt": f"Reply only OK. Request {index} {uuid.uuid4().hex}", "max_tokens": 4,
                "policy": "least_inflight",
            })
            if response.status_code != 200:
                raise RuntimeError(f"Inference request failed: HTTP {response.status_code} {response.text[:1000]}")
            response.raise_for_status()
            result = response.json()
            assert result["recorded"] and result["output"].strip()
            stored = client.get(f'http://127.0.0.1:18000/api/v1/requests/{result["request_id"]}')
            stored.raise_for_status()
            assert stored.json()["status"] == "success" and stored.json()["backend_id"] == backend_id
            results.append({"request_id": result["request_id"], "output": result["output"], "total_ms": result["timings"]["total_ms"]})
        return results

    def service(name, selector, nodeport=None):
        port = {"port": 8000, "targetPort": 8000}
        if nodeport:
            port["nodePort"] = nodeport
        apply({"apiVersion": "v1", "kind": "Service", "metadata": {"name": name, "namespace": namespace},
               "spec": {"selector": selector, "type": "NodePort" if nodeport else "ClusterIP", "ports": [port]}})

    try:
        nodes = json.loads(command(KUBE + ["get", "nodes", "-o", "json"]))
        check("isolated_kind", len(nodes["items"]) == 1 and nodes["items"][0]["metadata"]["name"] == "ew-recovery-lab-control-plane")
        client.get("http://127.0.0.1:18104/health").raise_for_status()
        if not args.skip_build:
            prepare(folder)
        command(KUBE + ["apply", "-f", str(OPERATOR / "config/crd/bases/aiinfra.example.com_elasticworkloads.yaml")])
        apply({"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": namespace}})
        created_namespace = True
        previous = json.loads(command(KUBE + ["-n", "ew-validation", "get", "deployment", "ew-controller", "-o", "json"]))["spec"]["replicas"]
        command(KUBE + ["-n", "ew-validation", "scale", "deployment/ew-controller", "--replicas=0"])
        paused = True
        command(KUBE + ["-n", "ew-validation", "wait", "--for=delete", "pod", "-l", "app=ew-controller", "--timeout=45s"])
        node_ip = nodes["items"][0]["status"]["addresses"][0]["address"]
        conf = folder / "relay.conf"
        conf.write_text(f"events {{}} http {{ server {{ listen 172.20.0.1:18200; location / {{ proxy_pass http://127.0.0.1:18000; }} }} server {{ listen 172.20.0.1:18205; listen 172.19.0.1:18205; location /{alias}/ {{ proxy_pass http://{node_ip}:31085/; proxy_buffering off; proxy_read_timeout 60s; }} location / {{ proxy_pass http://{node_ip}:31085; proxy_buffering off; proxy_read_timeout 60s; }} }} }}")
        command(["docker", "run", "-d", "--name", relay, "--network", "host", "--memory", "64m", "--cpus", "0.25", "-v", f"{conf}:/etc/nginx/nginx.conf:ro", "--entrypoint", "nginx", "nginx:alpine", "-g", "daemon off;"])
        relay_started = True
        service("serving", {"elasticworkload.aiinfra.example.com/name": "linked", "elasticworkload.aiinfra.example.com/workload": "inference"}, 31085)
        proxy_conf = 'events {} http { server { listen 8000; add_header X-EW-Pod $hostname always; location = /health { return 200 "ok"; } location / { proxy_pass http://172.20.0.1:18106; proxy_buffering off; proxy_read_timeout 60s; } } }'
        workload = {"apiVersion": "aiinfra.example.com/v1alpha1", "kind": "ElasticWorkload", "metadata": {"name": "linked", "namespace": namespace}, "spec": {
            "training": {"replicas": 3, "minReplicas": 2, "maxReplicas": 3, "gpuPerWorker": 0, "image": "busybox:1.36", "command": ["sh", "-c", "while true; do echo batch-placeholder; sleep 5; done"]},
            "inference": {"replicas": 1, "minReplicas": 1, "maxReplicas": 2, "gpuPerInstance": 0, "image": "nginx:alpine", "readinessHTTP": {"port": 8000, "path": "/health"}, "command": ["sh", "-c", "printf %s " + shlex.quote(proxy_conf) + " > /tmp/serving.conf; exec nginx -c /tmp/serving.conf -g 'daemon off;'"]},
            "scalingPolicy": {"targetMetric": "ttft_p95", "slo": 100000, "minHoldDuration": 0, "maxScaleStep": 1}}}
        apply(workload)
        apply({"apiVersion": "v1", "kind": "ServiceAccount", "metadata": {"name": "controller", "namespace": namespace}})
        apply({"apiVersion": "rbac.authorization.k8s.io/v1", "kind": "RoleBinding", "metadata": {"name": "controller", "namespace": namespace}, "subjects": [{"kind": "ServiceAccount", "name": "controller", "namespace": namespace}], "roleRef": {"kind": "ClusterRole", "name": "manager-role", "apiGroup": "rbac.authorization.k8s.io"}})
        def deploy(name, image, env=None, args=None, sa=None):
            container = {"name": name, "image": image, "imagePullPolicy": "Never", "resources": {"requests": {"cpu": "25m", "memory": "32Mi"}, "limits": {"cpu": "1", "memory": "256Mi"}}}
            if env: container["env"] = [{"name": k, "value": v} for k, v in env.items()]
            if args: container["args"] = args
            spec = {"containers": [container]}
            if sa: spec["serviceAccountName"] = sa
            apply({"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": name, "namespace": namespace}, "spec": {"replicas": 1, "selector": {"matchLabels": {"app": name}}, "template": {"metadata": {"labels": {"app": name}}, "spec": spec}}})
        deploy("router", "inference-platform/router:closure-v1", {"CONTROL_PLANE_URL": "http://172.20.0.1:18200", "STREAM_OPENAI": "true", "TTFT_MODEL": alias, "TTFT_WINDOW_SECONDS": "10"})
        service("router", {"app": "router"})
        deploy("controller", "ew-operator:closure-v1", args=["--watch-namespace=" + namespace, "--router-url=http://router:8000", "--metric-min-samples=3", "--metric-max-age=5s", "--leader-elect=false"], sa="controller")
        for name in ["router", "controller", "linked-inference", "linked-training"]:
            wait(lambda: bool(get("deployment", name)))
            command(KUBE + ["-n", namespace, "rollout", "status", "deployment/" + name, "--timeout=90s"])
        log = (folder / "router-forward.log").open("w")
        processes.append(subprocess.Popen(KUBE + ["-n", namespace, "port-forward", "service/router", "18201:8000"], stdout=log, stderr=subprocess.STDOUT))
        log.close()
        wait(lambda: client.get("http://127.0.0.1:18201/readyz").status_code == 200)
        model = client.post("http://127.0.0.1:18000/api/v1/models/upsert", json={"name": alias})
        model.raise_for_status()
        backend = client.post("http://127.0.0.1:18000/api/v1/backends", json={"name": alias, "engine": "openai", "url": f"http://172.20.0.1:18205/{alias}", "model_ids": [model.json()["id"]]})
        backend.raise_for_status()
        backend_id = backend.json()["id"]
        client.post(f"http://127.0.0.1:18000/api/v1/backends/{backend_id}/health", json={"healthy": True, "latency_ms": 1}).raise_for_status()
        wait(lambda: allocation(3, 1))
        check("baseline_3_1", True)
        check("empty_metric_rejected", client.get("http://127.0.0.1:18201/ttft_p95").status_code == 503)
        results = route(5)
        check("real_gpu_requests_and_audit", len(results) == 5, results)
        metric = client.get("http://127.0.0.1:18201/ttft_p95").json()
        check("real_model_ttft_window", metric["sample_count"] >= 3 and metric["ttft_p95_ms"] > 1 and metric["model"] == alias, metric)
        exported = client.get("http://127.0.0.1:18201/metrics/")
        exported.raise_for_status()
        check("prometheus_ttft_export", f'router_upstream_ttft_seconds_count{{model="{alias}"}} 5.0' in exported.text)
        command(KUBE + ["-n", namespace, "patch", "elasticworkload", "linked", "--type=merge", "-p", json.dumps({"spec": {"scalingPolicy": {"slo": 1}}})])
        route(3)
        wait(lambda: allocation(2, 2))
        check("metric_drives_scale_out_2_2", True, get("elasticworkload", "linked")["status"])
        wait(lambda: endpoint_count() == 2)
        check("ready_endpoints_discovered", True)
        hosts = set()
        deadline = time.monotonic() + 10
        probes = 0
        while time.monotonic() < deadline and len(hosts) < 2:
            with httpx.Client(trust_env=False, timeout=5) as probe:
                response = probe.get("http://172.20.0.1:18205/health")
                probes += 1
                if response.status_code == 200:
                    hosts.add(response.headers.get("x-ew-pod"))
            time.sleep(.1)
        check("service_routes_to_both_replicas", len(hosts) == 2 and None not in hosts, {"hosts": sorted(hosts), "probes": probes})
        results = route(2)
        check("scaled_service_still_infers", len(results) == 2, results)
        patch({"scalingPolicy": {"slo": 100000, "minHoldDuration": 60}})
        route(3)
        patch({"scalingPolicy": {"minHoldDuration": 0}})
        wait(lambda: allocation(3, 1))
        wait(lambda: endpoint_count() == 1)
        check("recovery_returns_allocation_3_1", True, get("elasticworkload", "linked")["status"])
        time.sleep(11)
        check("expired_window_rejected", client.get("http://127.0.0.1:18201/ttft_p95").status_code == 503)
        wait(lambda: any(row["type"] == "MetricsReady" and row["status"] == "False" for row in get("elasticworkload", "linked")["status"]["conditions"]))
        check("invalid_metric_freezes_allocation", allocation(3, 1))
        pods = json.loads(command(KUBE + ["-n", namespace, "get", "pods", "-l", "elasticworkload.aiinfra.example.com/workload=inference", "-o", "json"]))
        old_uid = pods["items"][0]["metadata"]["uid"]
        command(KUBE + ["-n", namespace, "delete", "pod", pods["items"][0]["metadata"]["name"], "--wait=false"])
        def replaced():
            rows = json.loads(command(KUBE + ["-n", namespace, "get", "pods", "-l", "elasticworkload.aiinfra.example.com/workload=inference", "-o", "json"]))["items"]
            return any(row["metadata"]["uid"] != old_uid and any(c["type"] == "Ready" and c["status"] == "True" for c in row["status"].get("conditions", [])) for row in rows)
        wait(replaced)
        wait(lambda: client.get("http://172.20.0.1:18205/health").status_code == 200)
        check("serving_pod_recreated", True)
        check("inference_after_recreation", len(route(3)) == 3)
        resources = get("deployment", "linked-inference")["spec"]["template"]["spec"]["containers"][0]["resources"]
        check("explicit_cpu_memory_reservations", resources["requests"] == {"cpu": "100m", "memory": "64Mi"} and resources["limits"] == {"cpu": "500m", "memory": "256Mi"}, resources)
        history = len(get("elasticworkload", "linked")["status"].get("scalingHistory", []))
        patch({"inference": {"resources": {"limits": {"memory": "384Mi"}}}})
        wait(lambda: template_available(memory="384Mi"))
        check("resource_limit_update_rolls_out", True)
        patch({"inference": {"image": "nginx:ew-closure"}})
        wait(lambda: template_available(image="nginx:ew-closure"))
        check("image_update_rolls_out_without_replanning", allocation(3, 1) and len(get("elasticworkload", "linked")["status"].get("scalingHistory", [])) == history)
        check("inference_after_template_updates", len(route(2)) == 2)
        for name, value in [("initial_budget_immutable", {"training": {"replicas": 2}}),
                            ("gpu_units_immutable", {"training": {"gpuPerWorker": 1}})]:
            rejected = subprocess.run(KUBE + ["-n", namespace, "patch", "elasticworkload", "linked", "--type=merge", "-p", json.dumps({"spec": value})], capture_output=True, text=True, timeout=10)
            check(name, rejected.returncode != 0 and "immutable" in rejected.stderr)
        patch({"inference": {"resources": {"requests": {"cpu": "2"}}}})
        wait(degraded)
        check("invalid_resources_are_reported_without_apply", allocation(3, 1) and get("deployment", "linked-inference")["spec"]["template"]["spec"]["containers"][0]["resources"]["requests"]["cpu"] == "100m")
        patch({"inference": {"resources": {"requests": {"cpu": "100m"}}}})
        patch({"scalingPolicy": {"slo": 1}})
        route(3)
        wait(lambda: allocation(2, 2))
        patch({"inference": {"maxReplicas": 1}})
        wait(degraded)
        check("incompatible_bounds_freeze_committed_target", allocation(2, 2))
        patch({"inference": {"maxReplicas": 2}, "scalingPolicy": {"slo": 100000, "minHoldDuration": 60}})
        route(3)
        patch({"scalingPolicy": {"minHoldDuration": 0}})
        wait(lambda: allocation(3, 1))
        wait(lambda: endpoint_count() == 1)
        wait(lambda: client.get("http://172.20.0.1:18205/health").status_code == 200)
        check("corrected_configuration_recovers", len(route(2)) == 2)
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        (folder / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        if created_namespace:
            for resource in ["pods", "deployments", "elasticworkloads", "events"]:
                try: (folder / f"{resource}.json").write_text(command(KUBE + ["-n", namespace, "get", resource, "-o", "json"]))
                except Exception: pass
        raise
    finally:
        errors = []
        if created_namespace:
            for name in ["controller", "router"]:
                try: (folder / f"{name}.log").write_text(command(KUBE + ["-n", namespace, "logs", "deployment/" + name]))
                except Exception: pass
        for process in processes:
            process.terminate()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill()
        if backend_id:
            try: client.delete(f"http://127.0.0.1:18000/api/v1/backends/{backend_id}").raise_for_status()
            except Exception as exc: errors.append(str(exc))
        if created_namespace:
            try:
                command(KUBE + ["-n", namespace, "delete", "elasticworkload", "linked", "--ignore-not-found", "--wait=true", "--timeout=30s"])
                command(KUBE + ["delete", "namespace", namespace, "--wait=true", "--timeout=60s"])
            except Exception as exc: errors.append(str(exc))
        if relay_started:
            try: command(["docker", "rm", "-f", relay])
            except Exception as exc: errors.append(str(exc))
        if paused:
            try: command(KUBE + ["-n", "ew-validation", "scale", "deployment/ew-controller", f"--replicas={previous}"])
            except Exception as exc: errors.append(str(exc))
        client.close()
        report["cleanup_errors"] = errors
        if errors: report["status"] = "failed"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        (folder / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"status": report["status"], "report": str(folder / "report.json"), "cleanup_errors": errors}), flush=True)
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
