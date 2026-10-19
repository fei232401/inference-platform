from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
import uuid

import httpx


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * quantile) - 1)], 3)


async def request(client: httpx.AsyncClient, args: argparse.Namespace, index: int) -> dict:
    prompt = f"Experiment {uuid.uuid4().hex}. " + args.prompt
    started = time.perf_counter()
    record = {"index": index, "http_status": None, "ttft_ms": None, "completion_tokens": None}
    try:
        if args.mode == "direct":
            payload = {
                "model": args.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": args.tokens,
                "ignore_eos": True,
                "stream": True,
                "stream_options": {"include_usage": True},
            }
            done = False
            content_seen = False
            async with client.stream("POST", args.url.rstrip("/") + "/v1/chat/completions", json=payload) as response:
                record["http_status"] = response.status_code
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        done = True
                        continue
                    event = json.loads(data)
                    if "error" in event:
                        raise RuntimeError("stream_error")
                    for choice in event.get("choices", []):
                        if choice.get("delta", {}).get("content"):
                            content_seen = True
                            if record["ttft_ms"] is None:
                                record["ttft_ms"] = (time.perf_counter() - started) * 1000
                    if event.get("usage"):
                        record.update({k: event["usage"].get(k) for k in ("prompt_tokens", "completion_tokens")})
            if not done or not content_seen or not isinstance(record["completion_tokens"], int):
                raise RuntimeError("incomplete_stream_or_missing_usage")
        else:
            response = await client.post(args.url.rstrip("/") + "/v1/route", json={
                "model_name": args.model, "prompt": prompt, "max_tokens": args.tokens,
                "policy": "least_inflight",
            })
            record["http_status"] = response.status_code
            response.raise_for_status()
            data = response.json()
            record.update({k: data.get("usage", {}).get(k) for k in ("prompt_tokens", "completion_tokens")})
            record["admission"] = data.get("decision", {}).get("score_snapshot", {}).get("admission")
        record["success"] = True
    except Exception as exc:
        record["success"] = False
        record["error"] = type(exc).__name__
    record["e2e_ms"] = round((time.perf_counter() - started) * 1000, 3)
    return record


async def run(args: argparse.Namespace) -> None:
    headers = {}
    if args.key_file:
        headers["X-API-Key"] = Path(args.key_file).read_text().strip()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "mode": args.mode, "url": args.url, "model": args.model,
        "max_tokens": args.tokens, "requests_per_level": args.requests,
        "warmup_requests": args.warmup, "prompt": args.prompt,
        "method": "closed_loop; unique prefix; client-observed first nonempty content; nearest-rank percentiles",
        "ignore_eos": args.mode == "direct", "levels": [], "status": "running",
    }
    async with httpx.AsyncClient(timeout=args.timeout, trust_env=False, headers=headers,
                                 limits=httpx.Limits(max_connections=max(args.concurrency) + 2)) as client:
        for index in range(args.warmup):
            warmup = await request(client, args, -index - 1)
            if not warmup["success"]:
                raise RuntimeError(f"warmup failed: {warmup}")
        for concurrency in args.concurrency:
            semaphore = asyncio.Semaphore(concurrency)

            async def bounded(index: int) -> dict:
                async with semaphore:
                    return await request(client, args, index)

            started = time.perf_counter()
            records = await asyncio.gather(*(bounded(i) for i in range(args.requests)))
            elapsed = time.perf_counter() - started
            successful = [r for r in records if r["success"]]
            tokens = sum(r["completion_tokens"] or 0 for r in successful)
            summary = {
                "concurrency": concurrency, "elapsed_seconds": round(elapsed, 3),
                "success": len(successful), "failed": len(records) - len(successful),
                "http_statuses": dict(Counter(str(r["http_status"]) for r in records)),
                "output_tokens": tokens, "output_tokens_per_second": round(tokens / elapsed, 3),
                "success_requests_per_second": round(len(successful) / elapsed, 3),
                "ttft_p50_ms": percentile([r["ttft_ms"] for r in successful if r["ttft_ms"] is not None], .5),
                "ttft_p95_ms": percentile([r["ttft_ms"] for r in successful if r["ttft_ms"] is not None], .95),
                "success_e2e_p95_ms": percentile([r["e2e_ms"] for r in successful], .95),
            }
            report["levels"].append({"summary": summary, "requests": records})
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps(summary), flush=True)
        report["status"] = "completed"
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["direct", "router"], default="direct")
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--key-file")
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--requests", type=int, default=16)
    parser.add_argument("--tokens", type=int, default=128)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--prompt", default="Explain how a Kubernetes controller reconciles desired state and actual state, including retries and readiness. Give a detailed answer.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 1 <= args.requests <= 256 or not 1 <= args.tokens <= 512 or not all(1 <= c <= 16 for c in args.concurrency) or args.warmup < 0:
        parser.error("requests 1..256, tokens 1..512, concurrency 1..16, warmup >= 0 required")
    if args.mode == "router" and not args.key_file:
        parser.error("router mode requires --key-file")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
