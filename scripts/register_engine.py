import argparse
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True)
parser.add_argument("--model", required=True)
parser.add_argument("--name", default="vllm-demo")
parser.add_argument("--api", default="http://127.0.0.1:18080")
args = parser.parse_args()
key = (ROOT / ".state/admin-key").read_text().strip()
with httpx.Client(base_url=args.api, headers={"X-API-Key": key}, timeout=30) as client:
    model = client.post("/api/v1/models/upsert", json={"name": args.model}).raise_for_status().json()
    entries = client.get("/api/v1/backends", params={"limit": 200}).raise_for_status().json()["items"]
    backend = next((row for row in entries if row["url"].rstrip("/") == args.url.rstrip("/")), None)
    if backend:
        client.post(f'/api/v1/backends/{backend["id"]}/models', json={"model_ids": [model["id"]]}).raise_for_status()
    else:
        backend = client.post("/api/v1/backends", json={"name": args.name, "url": args.url, "engine": "openai", "model_ids": [model["id"]]}).raise_for_status().json()
    print("Registered model and backend:", args.model, backend["name"])
