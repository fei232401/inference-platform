import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest


spec = importlib.util.spec_from_file_location("native_offload_validator", Path(__file__).parents[1] / "scripts/validate_native_offload.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


@pytest.mark.parametrize("restored_output,expected_code", [("OK", 0), ("garbled", 1)])
def test_cpu_restore_requires_correct_output_and_external_hit(monkeypatch, tmp_path, restored_output, expected_code):
    outputs = iter(["OK", "OK", restored_output])
    counters = iter([(0, 0), (1280, 0), (1280, 0), (1280, 1280)])

    class Client:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, **kwargs):
            output = next(outputs) if url.endswith("/v1/chat/completions") else "filler"
            return httpx.Response(200, request=httpx.Request("POST", url), json={
                "id": "synthetic", "choices": [{"message": {"content": output}}], "usage": {},
            })

    def snapshot(*args):
        native, external = next(counters)
        return {"counters": {"vllm:prefix_cache_hits_total": native, "vllm:external_prefix_cache_hits_total": external}, "offload_samples": []}

    monkeypatch.setattr(validator.httpx, "Client", lambda **kwargs: Client())
    monkeypatch.setattr(validator.time, "sleep", lambda value: None)
    monkeypatch.setattr(validator, "snapshot", snapshot)
    report = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["validate", "--url", "http://test", "--model", "test", "--output", str(report), "--rounds", "1"])
    with pytest.raises(SystemExit) as exited:
        validator.main()
    assert exited.value.code == expected_code
    data = json.loads(report.read_text())
    assert data["rounds"][0]["checks"]["restored_external_cache_hit"]
    assert data["status"] == ("passed" if expected_code == 0 else "failed")
