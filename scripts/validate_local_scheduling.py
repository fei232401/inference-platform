import argparse
import json
from pathlib import Path
import subprocess
import time
import uuid


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    context = "kind-ew-recovery-lab"
    base = ["kubectl", "--kubeconfig", args.kubeconfig, "--context", context, "--request-timeout=10s"]
    namespace = "fei-local-functional-" + uuid.uuid4().hex[:8]
    report = {"context": context, "namespace": namespace, "checks": [], "status": "running"}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    def kubectl(*arguments, body=None):
        return subprocess.run(base + list(arguments), input=json.dumps(body) if body is not None else None,
                              text=True, capture_output=True, check=True, timeout=30).stdout

    def save():
        output.write_text(json.dumps(report, indent=2) + "\n")

    def wait_for(name, predicate):
        until = time.monotonic() + 40
        while time.monotonic() < until:
            pod = json.loads(kubectl("-n", namespace, "get", "pod", name, "-o", "json"))
            if predicate(pod):
                return pod
            time.sleep(.5)
        raise RuntimeError(f"timeout waiting for {name}")

    def scheduled_condition(pod):
        return next((c for c in pod.get("status", {}).get("conditions", []) if c["type"] == "PodScheduled"), {})

    def create_pod(name, requests, limits=None):
        resources = {"requests": requests}
        if limits:
            resources["limits"] = limits
        kubectl("-n", namespace, "create", "-f", "-", body={
            "apiVersion": "v1", "kind": "Pod", "metadata": {"name": name},
            "spec": {"restartPolicy": "Never", "containers": [{
                "name": "probe", "image": "busybox:1.36", "imagePullPolicy": "Never",
                "command": ["sh", "-c", "echo local-functional-ok"], "resources": resources,
            }]},
        })

    created = False
    try:
        nodes = json.loads(kubectl("get", "nodes", "-o", "json"))["items"]
        if len(nodes) != 1 or nodes[0]["metadata"]["name"] != "ew-recovery-lab-control-plane":
            raise RuntimeError("unexpected cluster nodes")
        report["node_allocatable"] = nodes[0]["status"]["allocatable"]
        kubectl("create", "namespace", namespace)
        created = True
        create_pod("cpu-ok", {"cpu": "10m", "memory": "8Mi"})
        pod = wait_for("cpu-ok", lambda p: p.get("status", {}).get("phase") == "Succeeded")
        assert "local-functional-ok" in kubectl("-n", namespace, "logs", "cpu-ok")
        report["checks"].append({"name": "cpu_task_runs", "node": pod["spec"]["nodeName"], "passed": True})
        create_pod("memory-too-large", {"cpu": "10m", "memory": "1000Ti"})
        pod = wait_for("memory-too-large", lambda p: scheduled_condition(p).get("reason") == "Unschedulable")
        condition = scheduled_condition(pod)
        assert "Insufficient memory" in condition["message"]
        report["checks"].append({"name": "memory_shortage_stays_pending", "condition": condition, "passed": True})
        create_pod("gpu-unavailable", {"cpu": "10m", "memory": "8Mi", "nvidia.com/gpu": "1"}, {"nvidia.com/gpu": "1"})
        pod = wait_for("gpu-unavailable", lambda p: scheduled_condition(p).get("reason") == "Unschedulable")
        condition = scheduled_condition(pod)
        assert "Insufficient nvidia.com/gpu" in condition["message"]
        report["checks"].append({"name": "gpu_request_does_not_run_on_cpu_only_node", "condition": condition, "passed": True})
        kubectl("-n", namespace, "delete", "pod", "memory-too-large", "--wait=true")
        create_pod("memory-too-large", {"cpu": "10m", "memory": "8Mi"})
        wait_for("memory-too-large", lambda p: p.get("status", {}).get("phase") == "Succeeded")
        report["checks"].append({"name": "recreated_task_with_feasible_request_runs", "passed": True})
        report["events"] = json.loads(kubectl("-n", namespace, "get", "events", "-o", "json"))
        report["status"] = "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = str(exc)
        raise
    finally:
        if created:
            try:
                kubectl("delete", "namespace", namespace, "--wait=true", "--timeout=25s")
                report["cleaned_up"] = True
            except Exception as exc:
                report["cleaned_up"] = False
                report["cleanup_error"] = str(exc)
        save()
        print(json.dumps({k:v for k,v in report.items() if k != "events"}, indent=2))


if __name__ == "__main__":
    main()
