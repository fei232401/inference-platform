from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import math
import random
import re
import statistics
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "router"))

from src.admission import AdmissionController  # noqa: E402
from src.affinity import affinity_key  # noqa: E402

WORDS = ("cluster scheduler quota tenant replica gradient checkpoint prefill decode cache block token "
         "latency throughput admission router backend shard rollout canary failover topology bandwidth "
         "kernel memory tensor batch queue priority preemption budget window sample").split()


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * quantile) - 1)], 2)


def document(rng: random.Random, salt: str, words: int) -> str:
    body = " ".join(rng.choice(WORDS) for _ in range(words))
    return f"Reference document {salt}.\n{body}\n"


async def scrape(client: httpx.AsyncClient, url: str) -> dict[str, float]:
    text = (await client.get(url.rstrip("/") + "/metrics")).text
    values = {}
    for name in ("prefix_cache_queries_total", "prefix_cache_hits_total", "num_preemptions_total"):
        match = re.search(rf"^vllm:{name}{{[^}}]*}} ([0-9.e+]+)$", text, re.M)
        values[name] = float(match.group(1)) if match else 0.0
    return values


async def generate(client: httpx.AsyncClient, url: str, model: str, prompt: str, tokens: int) -> dict:
    payload = {
        "model": model, "messages": [{"role": "user", "content": prompt}],
        "temperature": 0, "max_tokens": tokens, "ignore_eos": True,
        "stream": True, "stream_options": {"include_usage": True},
    }
    started = time.perf_counter()
    record = {"ttft_ms": None, "prompt_tokens": None, "success": False}
    async with client.stream("POST", url.rstrip("/") + "/v1/chat/completions", json=payload) as response:
        response.raise_for_status()
        async for line in response.aiter_lines():
            if not line.startswith("data:") or line[5:].strip() == "[DONE]":
                continue
            event = json.loads(line[5:])
            for choice in event.get("choices", []):
                if choice.get("delta", {}).get("content") and record["ttft_ms"] is None:
                    record["ttft_ms"] = (time.perf_counter() - started) * 1000
            if event.get("usage"):
                record["prompt_tokens"] = event["usage"].get("prompt_tokens")
    record["e2e_ms"] = (time.perf_counter() - started) * 1000
    record["success"] = record["ttft_ms"] is not None
    return record


async def run_policy(client, args, policy: str, repetition: int) -> dict:
    salt = f"{policy}-{repetition}-{uuid.uuid4().hex[:8]}"
    rng = random.Random(args.seed * 1000 + repetition)
    docs = [document(rng, f"{salt}-{index}", args.doc_words) for index in range(args.documents)]
    sequence = [rng.randrange(args.documents) for _ in range(args.requests)]
    candidates = [{"backend_id": index + 1, "score": 1.0, "excluded": False} for index in range(len(args.backends))]
    admission = AdmissionController()
    round_robin = itertools.count()
    before = [await scrape(client, url) for url in args.backends]
    semaphore = asyncio.Semaphore(args.concurrency)

    async def one(index: int) -> dict:
        prompt = docs[sequence[index]] + f"Question {index}: summarize the document in one sentence."
        async with semaphore:
            if policy == "round_robin":
                backend = next(round_robin) % len(args.backends) + 1
                record = await generate(client, args.backends[backend - 1], args.model, prompt, args.tokens)
            else:
                key = affinity_key(prompt, args.prefix_chars) if policy == "prefix_affinity" else None
                with admission.reserve(candidates, policy, args.concurrency, {}, key, args.load_factor) as reservation:
                    backend = int(reservation.chosen["backend_id"])
                    record = await generate(client, args.backends[backend - 1], args.model, prompt, args.tokens)
        record.update({"index": index, "document": sequence[index], "backend": backend})
        return record

    started = time.perf_counter()
    records = await asyncio.gather(*(one(index) for index in range(args.requests)))
    elapsed = time.perf_counter() - started
    after = [await scrape(client, url) for url in args.backends]
    queries = sum(a["prefix_cache_queries_total"] - b["prefix_cache_queries_total"] for a, b in zip(after, before))
    hits = sum(a["prefix_cache_hits_total"] - b["prefix_cache_hits_total"] for a, b in zip(after, before))
    preemptions = sum(a["num_preemptions_total"] - b["num_preemptions_total"] for a, b in zip(after, before))
    ttft = [r["ttft_ms"] for r in records if r["success"]]
    share = Counter(r["backend"] for r in records)
    docs_per_backend = {backend: len({r["document"] for r in records if r["backend"] == backend}) for backend in share}
    summary = {
        "policy": policy, "repetition": repetition, "load_factor": args.load_factor if policy == "prefix_affinity" else None, "elapsed_seconds": round(elapsed, 2),
        "success": len(ttft), "failed": len(records) - len(ttft),
        "prefix_cache_hit_rate": round(hits / queries, 4) if queries else None,
        "prefix_cache_hit_tokens": int(hits), "prefix_cache_query_tokens": int(queries),
        "ttft_p50_ms": percentile(ttft, .5), "ttft_p95_ms": percentile(ttft, .95),
        "ttft_mean_ms": round(statistics.fmean(ttft), 2) if ttft else None,
        "requests_per_backend": dict(sorted(share.items())),
        "distinct_documents_per_backend": dict(sorted(docs_per_backend.items())),
        "preemptions": int(preemptions),
        "mean_prompt_tokens": round(statistics.fmean(r["prompt_tokens"] for r in records if r["prompt_tokens"]), 1),
    }
    return {"summary": summary, "requests": records}


async def main(args: argparse.Namespace) -> None:
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "config": {key: value for key, value in vars(args).items() if key != "output"},
        "method": ("closed loop; uniform random choice among shared documents; unique question suffix; "
                   "fresh document salt per run so earlier runs cannot warm the cache; policies interleaved; "
                   "hit rate from vLLM prefix_cache_hits_total / prefix_cache_queries_total deltas"),
        "runs": [], "status": "running",
    }
    async with httpx.AsyncClient(timeout=args.timeout, trust_env=False,
                                 limits=httpx.Limits(max_connections=args.concurrency * 2 + 4)) as client:
        for repetition in range(args.repetitions):
            for policy in args.policies:
                result = await run_policy(client, args, policy, repetition)
                report["runs"].append(result)
                output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
                print(json.dumps(result["summary"], ensure_ascii=False), flush=True)
    report["status"] = "completed"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--backends", nargs="+", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--policies", nargs="+", default=["round_robin", "least_inflight", "prefix_affinity"],
                        choices=["round_robin", "least_inflight", "prefix_affinity"])
    parser.add_argument("--documents", type=int, default=24)
    parser.add_argument("--doc-words", type=int, default=1200)
    parser.add_argument("--requests", type=int, default=240)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--tokens", type=int, default=16)
    parser.add_argument("--prefix-chars", type=int, default=1024)
    parser.add_argument("--load-factor", type=float, default=1.25)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--seed", type=int, default=20261019)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", required=True)
    asyncio.run(main(parser.parse_args()))
