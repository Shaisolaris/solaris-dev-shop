#!/usr/bin/env python3
"""M23 adapter (Grok self-validation): transcribes one M23 raw world bundle (wp-config.php, plugins.json, debug.log,
mysql-slow.log, qm-db.json, timings.csv, drop-in files) into G23's documented bundle schema solaris.wp-trace/1,
following the "from" column of wp-trace-diagnosis.md, runs `wp_trace_diag.py diagnose` (and `compare` when a
timings.csv holds before and after phases) and prints {"findings": [...], "adapter": {...}} for the M23 oracle.

Transcription only; it never attributes or interprets:
- a MySQL slow-log entry has no caller, so its component and caller are "unknown";
- a Query Monitor component "Plugin: x" / "Theme: x" / "Core" becomes plugin:x / theme:x / core; QM's file:line
  location has no field in the schema and is dropped (recorded in adapter.dropped);
- wp-config line numbers and response headers have no field in the schema and are dropped (recorded);
- a request's total_ms is required by the schema; for QM or slow-log data it is the sum of its query times (a stated
  lower bound, recorded); env {php, wp, host} is "unknown" (same for before and after);
- timings.csv: one request per sample (url, total_ms = ttfb_ms); measurement.warm_cache is true when every sample of a
  phase is HIT, false when every sample is MISS, otherwise null;
- if a source file cannot be parsed (truncated JSON, cut-off log), the bundle JSON itself is written cut off at the
  same relative point, as a malformed upload would be (tests the tool's input handling, not the adapter).
Usage: g23_adapter.py BUNDLE_DIR PYTHON TOOL"""
import csv, io, json, os, re, subprocess, sys

bdir, PY, TOOL = sys.argv[1:4]
rd = lambda rel: open(os.path.join(bdir, rel), encoding="utf-8").read() if os.path.exists(os.path.join(bdir, rel)) else None
dropped, broken, notes = [], [], []

cfg = {}
src = rd("wp-config.php")
if src:
    for m in re.finditer(r"define\(\s*'([A-Z0-9_]+)'\s*,\s*('(?:[^'\\]|\\.)*'|true|false|-?\d+)\s*\)", src):
        k, v = m.group(1), m.group(2)
        cfg[k] = True if v == "true" else False if v == "false" else v[1:-1] if v.startswith("'") else int(v)
    dropped.append("wp-config.php line numbers (no schema field)")

plugins = []
pj = rd("plugins.json")
if pj is not None:
    try:
        plugins = [p["name"] for p in json.loads(pj) if p.get("status") == "active"]
    except (ValueError, KeyError, TypeError):
        broken.append("plugins.json")

errors = []
dl = rd("wp-content/debug.log")
if dl is not None:
    errors = [l for l in dl.splitlines() if l.strip()]
    if dl and not dl.endswith("\n"):
        broken.append("wp-content/debug.log (cut off)")

dropins = sorted(f for f in ("advanced-cache.php", "object-cache.php", "db.php", "maintenance.php")
                 if os.path.exists(os.path.join(bdir, "wp-content", f)))
if rd("headers.txt") is not None:
    dropped.append("headers.txt response headers (no schema field)")

requests = []
qm = rd("qm-db.json")
if qm is not None:
    try:
        qs = []
        for q in json.loads(qm)["queries"]:
            c = q.get("component", "")
            m = re.match(r"(?i)\s*(plugin|mu-plugin|theme)\s*:\s*(\S+)", c)
            comp = f"{m.group(1).lower()}:{m.group(2)}" if m else ("core" if c.lower().startswith("core") else "unknown")
            qs.append({"sql": q["sql"], "ms": round(q["time"] * 1000, 6), "caller": q.get("caller", "unknown"), "component": comp})
        requests.append({"id": "qm-1", "url": "/", "total_ms": round(sum(q["ms"] for q in qs), 6), "queries": qs})
        dropped.append("qm-db.json location file:line (no schema field); qm-1 total_ms = sum of query ms (lower bound)")
    except (ValueError, KeyError, TypeError):
        broken.append("qm-db.json")

sl = rd("mysql-slow.log")
if sl is not None:
    qs, cur, sql = [], None, []
    for line in sl.splitlines():
        m = re.match(r"# Query_time:\s*([0-9.]+)", line)
        if m:
            cur, sql = float(m.group(1)), []
            continue
        if cur is not None and line and not line.startswith(("#", "SET timestamp", "use ")):
            sql.append(line)
            if line.rstrip().endswith(";"):
                qs.append({"sql": " ".join(sql).rstrip(";"), "ms": round(cur * 1000, 6), "caller": "unknown", "component": "unknown"})
                cur = None
    if cur is not None:
        broken.append("mysql-slow.log (entry cut off)")
    if qs:
        requests.append({"id": "slow-log", "url": "/", "total_ms": round(sum(q["ms"] for q in qs), 6), "queries": qs})
        dropped.append("mysql-slow.log has no caller: component and caller unknown; slow-log total_ms = sum of query ms (lower bound)")

base = {"schema": "solaris.wp-trace/1", "site": os.path.basename(bdir), "environment": "production",
        "source": "Grok M23 synthetic world bundle %s, transcribed by the M23 adapter; not a real site" % os.path.basename(bdir),
        "env": {"php": "unknown", "wp": "unknown", "host": "unknown"}, "wp_config": cfg, "dropins": dropins,
        "active_plugins": plugins, "system_cron": None, "php_errors": errors}


def write(name, doc):
    p = os.path.join(bdir, name)
    txt = json.dumps(doc, indent=1)
    if broken:
        txt = txt[: len(txt) * 2 // 3]
    open(p, "w", encoding="utf-8").write(txt)
    return p


def run(*args):
    cp = subprocess.run([PY, TOOL, *args, "--json"], capture_output=True, text=True, timeout=60,
                        env={"PATH": "/usr/bin:/bin", "HOME": bdir, "PYTHONDONTWRITEBYTECODE": "1"})
    sys.stderr.write(cp.stderr)
    try:
        return cp.returncode, json.loads(cp.stdout)
    except ValueError:
        return cp.returncode, None


tm = rd("timings.csv")
phases = {}
if tm is not None:
    for row in csv.DictReader(io.StringIO(tm)):
        phases.setdefault(row["phase"], []).append(row)
findings, adapter = [], {"dropped": dropped, "broken": broken}
if "before" in phases and "after" in phases:
    docs = {}
    for ph in ("before", "after"):
        rows = phases[ph]
        caches = {r["cache"] for r in rows}
        warm = True if caches == {"HIT"} else False if caches == {"MISS"} else None
        doc = dict(base, measurement={"tool": "timings.csv ttfb", "warm_cache": warm, "runs_per_url": len(rows), "concurrency": 1},
                   requests=requests + [{"id": r["run"], "url": r["url"], "total_ms": float(r["ttfb_ms"])} for r in rows])
        docs[ph] = write(f"g23-{ph}.json", doc)
    rc, rep = run("diagnose", docs["after"])
    findings += (rep or {}).get("findings", [])
    crc, crep = run("compare", docs["before"], docs["after"])
    findings.append({"code": "COMPARE (adapter wrapper of compare output)", "severity": "info" if crc in (0, 3) else "high",
                     "compare_exit": crc, "compare": crep})
    adapter.update(diagnose_exit=rc, compare_exit=crc)
else:
    rc, rep = run("diagnose", write("g23-bundle.json", dict(base, requests=requests)))
    findings += (rep or {}).get("findings", [])
    adapter.update(diagnose_exit=rc, report_parsed=rep is not None)
print(json.dumps({"findings": findings, "adapter": adapter}))
sys.exit(rc if rc in (0, 1) else rc)
