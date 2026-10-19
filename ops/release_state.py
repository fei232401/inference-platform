import fcntl
import getpass
import json
from pathlib import Path
import time
import uuid


class ReleaseStore:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.journal = self.folder / "release-pending.json"
        self.release = self.folder / "release.json"

    def __enter__(self):
        self.lock = (self.folder / "release.lock").open("a")
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.lock.close()
            raise RuntimeError("Another release is running") from None
        return self

    def __exit__(self, *args):
        self.lock.close()

    def atomic(self, path, value):
        temporary = path.with_suffix(".tmp")
        with temporary.open("w") as handle:
            json.dump(value, handle)
            handle.flush()
            import os
            os.fsync(handle.fileno())
        temporary.replace(path)

    def audit(self, event, **fields):
        with (self.folder / "release-audit.jsonl").open("a") as handle:
            handle.write(json.dumps({"at": time.time(), "actor": getpass.getuser(), "event": event, **fields}) + "\n")

    def recover(self, restore):
        if not self.journal.exists():
            return False
        pending = json.loads(self.journal.read_text())
        current = json.loads(self.release.read_text()) if self.release.exists() else {}
        if current.get("transaction_id") == pending["id"]:
            self.journal.unlink()
            return False
        previous = pending.get("previous")
        if not previous:
            raise RuntimeError("Interrupted first release has no known healthy image; manual recovery required")
        restore(previous["tag"])
        self.audit("recovered", target=pending["tag"], restored=previous["tag"])
        self.journal.unlink()
        return True

    def begin(self, tag):
        previous = json.loads(self.release.read_text()) if self.release.exists() else None
        pending = {"id": uuid.uuid4().hex, "tag": tag, "previous": previous}
        self.atomic(self.journal, pending)
        self.audit("started", target=tag, transaction_id=pending["id"])
        return pending

    def commit(self, pending):
        self.atomic(self.release, {"tag": pending["tag"], "previous": (pending["previous"] or {}).get("tag"), "transaction_id": pending["id"], "deployed_at": time.time()})
        self.audit("succeeded", target=pending["tag"])
        self.journal.unlink()
