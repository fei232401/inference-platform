from dataclasses import dataclass
import json
import os
from pathlib import Path
import time

import httpx

SERVICE_ACCOUNT = Path("/var/run/secrets/kubernetes.io/serviceaccount")


@dataclass(frozen=True)
class Endpoint:
    pod: str
    url: str
    ready: bool
    terminating: bool


@dataclass(frozen=True)
class Action:
    kind: str
    name: str
    backend_id: int | None = None
    url: str | None = None


def endpoints_from_slices(slices, port_name=None, scheme="http"):
    found = {}
    for item in slices:
        ports = item.get("ports") or []
        port = next((p for p in ports if port_name is None or p.get("name") == port_name), None)
        if port is None or port.get("port") is None:
            continue
        for endpoint in item.get("endpoints") or []:
            pod = (endpoint.get("targetRef") or {}).get("name")
            addresses = endpoint.get("addresses") or []
            if not pod or not addresses:
                continue
            conditions = endpoint.get("conditions") or {}
            current = Endpoint(
                pod=pod,
                url=f"{scheme}://{addresses[0]}:{port['port']}",
                ready=conditions.get("ready") is True and conditions.get("terminating") is not True,
                terminating=conditions.get("terminating") is True,
            )
            previous = found.get(pod)
            if previous is None or (current.ready and not previous.ready):
                found[pod] = current
    return found


def plan(endpoints, backends, prefix, absent_since, now, retire_seconds):
    actions = []
    managed = {row["name"]: row for row in backends if row["name"].startswith(prefix)}
    wanted = {prefix + pod: endpoint for pod, endpoint in endpoints.items()}
    for name, endpoint in sorted(wanted.items()):
        row = managed.get(name)
        if not endpoint.ready:
            continue
        if row is None:
            actions.append(Action("create", name, url=endpoint.url))
            continue
        if row["url"].rstrip("/") != endpoint.url:
            actions.append(Action("update_url", name, row["id"], endpoint.url))
        if row["state"] != "active":
            actions.append(Action("activate", name, row["id"]))
    for name, row in sorted(managed.items()):
        endpoint = wanted.get(name)
        if endpoint is not None and endpoint.ready:
            continue
        since = absent_since.get(name, now)
        if row["state"] == "active":
            actions.append(Action("drain", name, row["id"]))
        elif row["state"] == "draining" and now - since >= retire_seconds:
            actions.append(Action("disable", name, row["id"]))
    return actions


def track_absence(endpoints, backends, prefix, absent_since, now):
    ready = {prefix + pod for pod, endpoint in endpoints.items() if endpoint.ready}
    result = {}
    for row in backends:
        name = row["name"]
        if name.startswith(prefix) and name not in ready and row["state"] != "disabled":
            result[name] = absent_since.get(name, now)
    return result


class Discovery:
    def __init__(self, api, key, kube_api, namespace, service, model, folder,
                 prefix=None, port_name=None, retire_seconds=30.0, kube_token=None, kube_ca=None, transport=None):
        self.api, self.key = api.rstrip("/"), key
        self.kube_api, self.namespace, self.service = kube_api.rstrip("/"), namespace, service
        self.model, self.port_name, self.retire_seconds = model, port_name, retire_seconds
        self.prefix = prefix or f"k8s:{namespace}/{service}/"
        self.kube_token, self.kube_ca, self.transport = kube_token, kube_ca, transport
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        path = self.folder / "discovery-state.json"
        self.absent_since = json.loads(path.read_text()) if path.exists() else {}
        self.model_id = None

    def slices(self):
        headers = {"Authorization": f"Bearer {self.kube_token}"} if self.kube_token else {}
        params = {"labelSelector": f"kubernetes.io/service-name={self.service}"}
        url = f"{self.kube_api}/apis/discovery.k8s.io/v1/namespaces/{self.namespace}/endpointslices"
        with httpx.Client(headers=headers, verify=self.kube_ca or True, timeout=5, trust_env=False, transport=self.transport) as client:
            return client.get(url, params=params).raise_for_status().json().get("items", [])

    def backends(self, client):
        rows, offset = [], 0
        while True:
            page = client.get("/api/v1/backends", params={"limit": 200, "offset": offset, "name_like": self.prefix}).raise_for_status().json()
            rows.extend(row for row in page["items"] if row["name"].startswith(self.prefix))
            if not page["meta"]["has_more"]:
                return rows
            offset += len(page["items"])

    def apply(self, client, action):
        if action.kind == "create":
            if self.model_id is None:
                self.model_id = client.post("/api/v1/models/upsert", json={"name": self.model}).raise_for_status().json()["id"]
            client.post("/api/v1/backends", json={"name": action.name, "url": action.url, "engine": "openai",
                                                  "model_ids": [self.model_id]}).raise_for_status()
        elif action.kind == "update_url":
            client.patch(f"/api/v1/backends/{action.backend_id}", json={"url": action.url}).raise_for_status()
        else:
            target = {"activate": "active", "drain": "draining", "disable": "disabled"}[action.kind]
            client.post(f"/api/v1/backends/{action.backend_id}/state", json={"state": target}).raise_for_status()

    def cycle(self):
        now = time.time()
        endpoints = endpoints_from_slices(self.slices(), self.port_name)
        with httpx.Client(base_url=self.api, headers={"X-API-Key": self.key}, timeout=5, trust_env=False, transport=self.transport) as client:
            backends = self.backends(client)
            self.absent_since = track_absence(endpoints, backends, self.prefix, self.absent_since, now)
            actions = plan(endpoints, backends, self.prefix, self.absent_since, now, self.retire_seconds)
            for action in actions:
                self.apply(client, action)
                with (self.folder / "discovery-events.jsonl").open("a") as output:
                    output.write(json.dumps({"at": now, "action": action.kind, "name": action.name,
                                             "backend_id": action.backend_id, "url": action.url}) + "\n")
        temporary = self.folder / "discovery-state.tmp"
        temporary.write_text(json.dumps(self.absent_since))
        temporary.replace(self.folder / "discovery-state.json")
        (self.folder / "heartbeat").write_text(str(now))
        return {"endpoints": len(endpoints), "ready": sum(e.ready for e in endpoints.values()), "actions": [a.kind for a in actions]}


def main():
    token_file = Path(os.getenv("KUBE_TOKEN_FILE", SERVICE_ACCOUNT / "token"))
    ca_file = Path(os.getenv("KUBE_CA_FILE", SERVICE_ACCOUNT / "ca.crt"))
    discovery = Discovery(
        api=os.getenv("CONTROL_PLANE_URL", "http://api:8000"),
        key=Path(os.environ["ADMIN_KEY_FILE"]).read_text().strip(),
        kube_api=os.getenv("KUBE_API", "https://kubernetes.default.svc"),
        namespace=os.environ["DISCOVERY_NAMESPACE"],
        service=os.environ["DISCOVERY_SERVICE"],
        model=os.environ["DISCOVERY_MODEL"],
        folder=os.getenv("DISCOVERY_STATE_DIR", "/state"),
        port_name=os.getenv("DISCOVERY_PORT_NAME") or None,
        retire_seconds=float(os.getenv("DISCOVERY_RETIRE_SECONDS", "30")),
        kube_token=token_file.read_text().strip() if token_file.exists() else None,
        kube_ca=str(ca_file) if ca_file.exists() else None,
    )
    while True:
        try:
            print(json.dumps({"event": "discovery_cycle", **discovery.cycle(), "at": time.time()}), flush=True)
        except Exception as exc:
            print(json.dumps({"event": "discovery_cycle_failed", "error_type": type(exc).__name__, "error": str(exc)[:200]}), flush=True)
        time.sleep(float(os.getenv("DISCOVERY_INTERVAL_SECONDS", "5")))


if __name__ == "__main__":
    main()
