# M11 probe (Grok self-validation): telemetry split across two sources per minute, and two sources with equal counts by chance.
import json, subprocess, sys, tempfile
from pathlib import Path
REPO = Path(sys.argv[1]); T = REPO / "employees/infrastructure/site-reliability-engineer/incident_slo.py"
d = Path(tempfile.mkdtemp(prefix="m11ps-", dir="/tmp"))
def m(i): return "2026-09-07T13:%02d:00Z" % i
def go(name, tel):
    b = {"schema": "solaris.incident-bundle/1", "service": "ledger-sync", "window": {"start": m(0), "end": "2026-09-07T14:00:00Z"}, "slo": {"objective": 0.99}, "telemetry": tel, "events": []}
    p = d / (name + ".json"); p.write_text(json.dumps(b)); cp = subprocess.run([sys.executable, str(T), "report", str(p), "--json"], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    r = json.loads(cp.stdout) if cp.returncode == 0 else {}
    print(name, "rc", cp.returncode, {k: r.get("slo", {}).get(k) for k in ("status", "good", "total", "availability", "coverage", "measured_minutes")}, r.get("missing_telemetry", {}).get("conflicting_minutes"), r.get("labels"), cp.stderr[-150:])
go("split_two_sources_every_minute", [dict(minute=m(i), good=g, total=500, source=s) for i in range(60) for s, g in (("lb-0", 500), ("lb-1", 480 if i == 30 else 500))])
# two load balancers whose counts happen to be equal for a minute: true traffic is 2x, tool counts it once (documented duplicate rule)
go("equal_counts_two_sources", [dict(minute=m(i), good=500, total=500, source=s) for i in range(60) for s in ("lb-0", "lb-1")])
import shutil; shutil.rmtree(d)
