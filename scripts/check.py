import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
output = ROOT / "artifacts"
output.mkdir(exist_ok=True)
environment = dict(os.environ)
if "TEST_DATABASE_DSN" not in environment:
    raise SystemExit("Set TEST_DATABASE_DSN to an isolated database ending in _test")
environment["SCHEMA_DIR"] = str(ROOT / "db")
environment.pop("SKIP_DB_TESTS", None)
for name in ["api", "router"]:
    report = output / f"{name}-tests.xml"
    subprocess.run([sys.executable, "-m", "pytest", "-q", f"--junitxml={report}"], cwd=ROOT / "services" / name, env=environment, check=True)
    if any(int(node.get("skipped", "0")) for node in ET.parse(report).iter("testsuite")):
        raise SystemExit(f"{name}: skipped tests are not accepted")
subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT, check=True)
subprocess.run(["npm", "test"], cwd=ROOT / "web", check=True)
subprocess.run(["npm", "run", "build"], cwd=ROOT / "web", check=True)
