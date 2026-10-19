import json
import os
from pathlib import Path
import signal
import subprocess
import time

import httpx


ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".state/engine-forwards.json"
ENDPOINTS = [("127.0.0.1", 18104), ("172.19.0.1", 18105), ("172.20.0.1", 18106)]


def healthy():
    try:
        with httpx.Client(timeout=2, trust_env=False) as client:
            return all(client.get(f"http://{address}:{port}/health").status_code == 200 for address, port in ENDPOINTS)
    except httpx.HTTPError:
        return False


def main():
    if healthy():
        print("Both local engine forwards are healthy")
        return
    if STATE.exists():
        for old in json.loads(STATE.read_text()):
            try:
                command = Path(f'/proc/{old["pid"]}/cmdline').read_bytes().split(b"\0")
                if b"service/vllm-3b-service" in command and f'{old["port"]}:8000'.encode() in command:
                    os.kill(old["pid"], signal.SIGTERM)
            except (FileNotFoundError, ProcessLookupError):
                pass
    time.sleep(.3)
    folder = ROOT / "artifacts/engine-forwards"
    folder.mkdir(parents=True, exist_ok=True)
    children = []
    for address, port in ENDPOINTS:
        with (folder / f"{port}.log").open("a") as output:
            child = subprocess.Popen([
                "kubectl", "--context", "k3d-ai-cluster", "--server=https://127.0.0.1:46121",
                "-n", "ai-platform", "port-forward", f"--address={address}",
                "service/vllm-3b-service", f"{port}:8000",
            ], stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            children.append({"pid": child.pid, "address": address, "port": port})
    STATE.parent.mkdir(exist_ok=True, mode=0o700)
    STATE.write_text(json.dumps(children, indent=2) + "\n")
    for _ in range(30):
        if healthy():
            print("Both local engine forwards are healthy")
            return
        time.sleep(.5)
    raise RuntimeError(f"Engine forwarding unavailable; inspect {folder}")


if __name__ == "__main__":
    main()
