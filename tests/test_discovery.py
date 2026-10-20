import json
from pathlib import Path
import tempfile
import unittest

import httpx

from ops.discovery import Discovery, Endpoint, endpoints_from_slices, plan, track_absence

PREFIX = "k8s:ns/svc/"


def endpoint_slice(*rows, port=8000):
    return {"ports": [{"name": "http", "port": port}], "endpoints": [
        {"addresses": [ip], "targetRef": {"name": pod}, "conditions": {"ready": ready, "terminating": terminating}}
        for pod, ip, ready, terminating in rows]}


def backend(id_, pod, state="active", url=None):
    return {"id": id_, "name": PREFIX + pod, "url": url or f"http://10.0.0.{id_}:8000", "state": state}


class EndpointTests(unittest.TestCase):
    def test_reads_ready_and_terminating_endpoints(self):
        found = endpoints_from_slices([endpoint_slice(("a", "10.0.0.1", True, False), ("b", "10.0.0.2", False, True))])
        self.assertEqual(found["a"], Endpoint("a", "http://10.0.0.1:8000", True, False))
        self.assertFalse(found["b"].ready)
        self.assertTrue(found["b"].terminating)

    def test_terminating_endpoint_is_never_ready(self):
        found = endpoints_from_slices([endpoint_slice(("a", "10.0.0.1", True, True))])
        self.assertFalse(found["a"].ready)

    def test_ready_copy_wins_across_slices(self):
        found = endpoints_from_slices([endpoint_slice(("a", "10.0.0.1", False, False)), endpoint_slice(("a", "10.0.0.1", True, False))])
        self.assertTrue(found["a"].ready)


class PlanTests(unittest.TestCase):
    def run_plan(self, endpoints, backends, absent=None, now=100.0, retire=30.0):
        return [(a.kind, a.name.removeprefix(PREFIX)) for a in plan(endpoints, backends, PREFIX, absent or {}, now, retire)]

    def test_new_ready_pod_is_registered(self):
        self.assertEqual(self.run_plan({"a": Endpoint("a", "http://1:8000", True, False)}, []), [("create", "a")])

    def test_starting_pod_is_not_registered(self):
        self.assertEqual(self.run_plan({"a": Endpoint("a", "http://1:8000", False, False)}, []), [])

    def test_terminating_pod_is_drained_immediately_then_disabled_after_grace(self):
        endpoints = {"a": Endpoint("a", "http://10.0.0.1:8000", False, True)}
        self.assertEqual(self.run_plan(endpoints, [backend(1, "a")]), [("drain", "a")])
        draining = [backend(1, "a", "draining")]
        self.assertEqual(self.run_plan({}, draining, {PREFIX + "a": 90.0}), [])
        self.assertEqual(self.run_plan({}, draining, {PREFIX + "a": 60.0}), [("disable", "a")])

    def test_returning_pod_is_reactivated_with_new_address(self):
        endpoints = {"a": Endpoint("a", "http://10.0.0.9:8000", True, False)}
        self.assertEqual(self.run_plan(endpoints, [backend(1, "a", "disabled")]), [("update_url", "a"), ("activate", "a")])

    def test_unmanaged_backends_are_never_touched(self):
        manual = {"id": 7, "name": "vllm-demo", "url": "http://x", "state": "active"}
        self.assertEqual(self.run_plan({}, [manual]), [])

    def test_absence_clock_starts_once_and_clears_on_disable(self):
        absent = track_absence({}, [backend(1, "a", "draining")], PREFIX, {}, 50.0)
        self.assertEqual(absent, {PREFIX + "a": 50.0})
        self.assertEqual(track_absence({}, [backend(1, "a", "draining")], PREFIX, absent, 80.0), absent)
        self.assertEqual(track_absence({}, [backend(1, "a", "disabled")], PREFIX, absent, 90.0), {})


class CycleTests(unittest.TestCase):
    def test_full_cycle_against_fake_cluster_and_control_plane(self):
        slices = [endpoint_slice(("pod-a", "10.0.0.1", True, False), ("pod-b", "10.0.0.2", False, True))]
        backends = [backend(2, "pod-b"), {"id": 9, "name": "manual", "url": "http://m", "state": "active"}]
        calls = []

        def handler(request):
            path = request.url.path
            calls.append((request.method, path, json.loads(request.content) if request.content else None))
            if "endpointslices" in path:
                assert request.url.params["labelSelector"] == "kubernetes.io/service-name=svc"
                return httpx.Response(200, json={"items": slices})
            if path == "/api/v1/backends" and request.method == "GET":
                return httpx.Response(200, json={"items": backends, "meta": {"has_more": False}})
            if path == "/api/v1/models/upsert":
                return httpx.Response(200, json={"id": 5})
            return httpx.Response(200, json={})

        with tempfile.TemporaryDirectory() as folder:
            discovery = Discovery("http://api", "key", "http://kube", "ns", "svc", "model-x", folder, transport=httpx.MockTransport(handler))
            result = discovery.cycle()
            self.assertEqual(result["actions"], ["create", "drain"])
            writes = [(m, p, b) for m, p, b in calls if m != "GET"]
            self.assertIn(("POST", "/api/v1/backends", {"name": PREFIX + "pod-a", "url": "http://10.0.0.1:8000", "engine": "openai", "model_ids": [5]}), writes)
            self.assertIn(("POST", "/api/v1/backends/2/state", {"state": "draining"}), writes)
            self.assertNotIn("/api/v1/backends/9/state", [p for _, p, _ in writes])
            state = json.loads((Path(folder) / "discovery-state.json").read_text())
            self.assertIn(PREFIX + "pod-b", state)
            self.assertEqual(len((Path(folder) / "discovery-events.jsonl").read_text().splitlines()), 2)


if __name__ == "__main__":
    unittest.main()
