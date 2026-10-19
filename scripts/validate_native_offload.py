import argparse
import json
from pathlib import Path
import time
import uuid

import httpx


def snapshot(client, url):
    response = client.get(url + "/metrics")
    response.raise_for_status()
    values = {}
    samples = []
    for line in response.text.splitlines():
        if line.startswith(("vllm:prefix_cache_hits_total{", "vllm:external_prefix_cache_hits_total{")):
            values[line.split("{")[0]] = float(line.split()[-1])
        if not line.startswith("#") and "offload" in line.lower():
            samples.append(line)
    return {"counters": values, "offload_samples": samples}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.rounds <= 4:
        parser.error("rounds must be 1..4")
    url = args.url.rstrip("/")
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    report = {"status": "running", "method": "cold, warm GPU hit, two distinct long fillers, CPU restore; no cache salts", "rounds": []}
    try:
        with httpx.Client(timeout=90, trust_env=False) as client:
            def chat(prompt):
                response = client.post(url + "/v1/chat/completions", json={
                    "model": args.model, "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0, "seed": 42, "max_tokens": 8,
                })
                response.raise_for_status()
                data = response.json()
                time.sleep(.3)
                return {"id": data["id"], "output": data["choices"][0]["message"]["content"],
                        "usage": data.get("usage"), "metrics": snapshot(client, url)}

            for index in range(args.rounds):
                nonce = uuid.uuid4().hex
                prompt = f"Local CPU restore test {nonce}.\n" + "".join(
                    f"Record {i}: controllers reconcile desired state and actual state using retries and readiness.\n" for i in range(75)
                ) + "\nReply with OK only."
                result = {"index": index, "cold": chat(prompt), "warm_gpu": chat(prompt), "fillers": []}
                report["rounds"].append(result)
                for _ in range(2):
                    filler = f"Distinct eviction filler {uuid.uuid4().hex}. " + "token " * 4200
                    response = client.post(url + "/v1/completions", json={
                        "model": args.model, "prompt": filler, "max_tokens": 1, "temperature": 0,
                    })
                    response.raise_for_status()
                    data = response.json()
                    result["fillers"].append({"id": data["id"], "usage": data.get("usage")})
                time.sleep(.5)
                result["before_restore"] = snapshot(client, url)
                result["restored"] = chat(prompt)
                first, warm, before, restored = result["cold"], result["warm_gpu"], result["before_restore"], result["restored"]
                delta = lambda name: restored["metrics"]["counters"].get(name, 0) - before["counters"].get(name, 0)
                result["checks"] = {
                    "cold_expected_output": first["output"].strip() == "OK",
                    "warm_output_equal": first["output"] == warm["output"],
                    "warm_native_cache_hit": warm["metrics"]["counters"].get("vllm:prefix_cache_hits_total", 0) > first["metrics"]["counters"].get("vllm:prefix_cache_hits_total", 0),
                    "restored_output_equal": first["output"] == restored["output"],
                    "restored_external_cache_hit": delta("vllm:external_prefix_cache_hits_total") > 0,
                    "restored_no_native_cache_hit": delta("vllm:prefix_cache_hits_total") == 0,
                }
                result["restored_external_tokens"] = delta("vllm:external_prefix_cache_hits_total")
                print(json.dumps({"round": index, "checks": result["checks"], "external_tokens": result["restored_external_tokens"]}), flush=True)
                path.write_text(json.dumps(report, indent=2) + "\n")
            report["status"] = "passed" if all(all(r["checks"].values()) for r in report["rounds"]) else "failed"
    except Exception as exc:
        report["status"] = "failed"
        report["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        path.write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
