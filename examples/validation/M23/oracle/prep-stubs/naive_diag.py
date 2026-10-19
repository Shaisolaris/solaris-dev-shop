"""M23 naive stub (Grok-made, not a candidate): blames every plugin named on any log line, picks the slow-query
culprit by query count, flags any 'true' define, substring-matches slugs, and computes speedup from all rows."""
import csv, json, os, re, sys
b = sys.argv[1]; out = []
rd = lambda p: open(os.path.join(b, p), encoding="utf-8", errors="replace").read() if os.path.exists(os.path.join(b, p)) else ""
plugins = [p["name"] for p in json.loads(rd("plugins.json") or "[]")]
for i, ln in enumerate(rd("wp-content/debug.log").splitlines(), 1):
    for slug in sorted(set(re.findall(r"/plugins/([\w-]+)/", ln))):
        out.append({"id": f"CONFLICT-{slug}", "severity": "Critical", "category": "Conflict", "title": f"Plugin conflict caused by {slug}",
                    "detail": ln, "location": f"wp-content/debug.log:{i}"})
tables = {}
for m in re.finditer(r"# Query_time: ([\d.]+).*?\n(?:SET timestamp=\d+;\n)?(.+)", rd("mysql-slow.log")):
    t = re.search(r"(?:FROM|INTO)\s+(wp_\w+)", m.group(2))
    if t:
        tables.setdefault(t.group(1), []).append(float(m.group(1)))
if tables:
    top = max(tables, key=lambda k: len(tables[k]))
    slug = next((p for p in plugins if p.replace("-", "_").split("_")[0] in top), top)
    out.append({"id": "SLOW-1", "severity": "Warning", "category": "Performance", "title": f"Slow queries from {slug}",
                "detail": f"{len(tables[top])} slow queries on {top}, worst {max(tables[top])}s", "location": "mysql-slow.log"})
for i, ln in enumerate(rd("wp-config.php").splitlines(), 1):
    m = re.search(r"define\(\s*'(\w+)',\s*true", ln)
    if m:
        out.append({"id": f"CFG-{m.group(1)}", "severity": "Warning", "category": "Config", "title": f"{m.group(1)} is enabled", "location": f"wp-config.php:{i}"})
rows = list(csv.DictReader(rd("timings.csv").splitlines())) if rd("timings.csv") else []
if rows:
    mean = lambda ph: sum(float(r["ttfb_ms"]) for r in rows if r["phase"] == ph) / max(1, sum(r["phase"] == ph for r in rows))
    out.append({"id": "PERF-SPEEDUP", "severity": "Info", "category": "Performance", "title": f"Speedup {mean('before') / mean('after'):.1f}x faster after fix"})
print(json.dumps(out))
