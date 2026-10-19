import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ops.release_state import ReleaseStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", nargs="?")
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--recover-only", action="store_true")
    args = parser.parse_args()
    if not args.recover_only and (not args.tag or not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}", args.tag)):
        parser.error("A valid image tag is required")
    load_dotenv(ROOT / ".env")
    environment = dict(os.environ)

    def compose(tag, *commands):
        subprocess.run(["docker", "compose", *commands], cwd=ROOT, env=dict(environment, IMAGE_TAG=tag), check=True)

    def restore(tag):
        compose(tag, "up", "-d", "--no-build", "--wait", "--wait-timeout", "90", "api", "router", "web", "monitor")

    (ROOT / ".state/probes").mkdir(mode=0o700, parents=True, exist_ok=True)
    with ReleaseStore(ROOT / ".state") as store:
        store.recover(restore)
        if args.recover_only:
            print("Interrupted release recovery completed")
            return
        tag = args.tag
        compose(tag, "up", "-d", "--wait", "postgres")
        if args.build:
            compose(tag, "build", "--build-arg", "GIT_SHA=" + tag, "api", "router", "web")
        pending = store.begin(tag)
        try:
            compose(tag, "run", "--rm", "init")
            restore(tag)
        except subprocess.CalledProcessError:
            store.audit("failed", target=tag)
            store.recover(restore)
            raise
        store.commit(pending)
    print("Ready at http://127.0.0.1:18080; image tag:", tag)


if __name__ == "__main__":
    main()
