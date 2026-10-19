"""M23 reference stub (Grok-made, not a candidate; shows the oracle is passable). Static, offline parser."""
import csv, json, os, re, statistics, sys
b = sys.argv[1]; out = []
def rd(p):
    q = os.path.join(b, p)
    return open(q, encoding="utf-8", errors="replace").read() if os.path.exists(q) else None
def F(id_, sev, cat, title, detail, loc):
    out.append({"id": id_, "severity": sev, "category": cat, "title": title, "summary": "", "detail": detail, "location": loc})
try:
    plist = json.loads(rd("plugins.json") or "[]")
except ValueError:
    plist = []; F("DIAG-INPUT", "Info", "Diagnostics", "plugins.json unreadable; plugin attribution limited", "", "plugins.json")
active = {p.get("name") for p in plist if isinstance(p, dict) and p.get("status") in ("active", "must-use")}
cfg = (rd("wp-config.php") or "").splitlines()
defs = {}
for i, ln in enumerate(cfg, 1):
    m = re.match(r"\s*define\(\s*'(\w+)',\s*(.+?)\s*\);", ln)
    if m:
        defs[m.group(1)] = (m.group(2).strip("'\""), i)
def bytes_of(v):
    m = re.match(r"(\d+)\s*([KMG]?)", v or "", re.I)
    return int(m.group(1)) * {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}[m.group(2).upper()] if m else None
for i, ln in enumerate((rd("wp-content/debug.log") or "").splitlines(), 1):
    m = re.search(r"PHP Fatal error:\s+Cannot redeclare (\w+)\(\) \(previously declared in (\S+?):(\d+)\) in (\S+) on line (\d+)", ln)
    if m:
        s1 = re.search(r"/(?:plugins|themes)/([\w-]+)/", m.group(2)); s2 = re.search(r"/(?:plugins|themes)/([\w-]+)/", m.group(4))
        a, c = (s1.group(1) if s1 else "?"), (s2.group(1) if s2 else "?")
        F("CONFLICT-REDECLARE", "Critical", "Plugin conflict", f"Function {m.group(1)}() declared by both {a} and {c}",
          f"{c} redeclares {m.group(1)}() at {m.group(4).split('/wp-content/')[-1]} line {m.group(5)}; first declared in "
          f"{m.group(2).split('/wp-content/')[-1]}:{m.group(3)}", f"{m.group(4).split('/wp-content/')[-1]}:{m.group(5)}")
        continue
    m = re.search(r"Allowed memory size of (\d+) bytes exhausted.* in (\S+) on line (\d+)", ln)
    if m and "WP_MEMORY_LIMIT" in defs and bytes_of(defs["WP_MEMORY_LIMIT"][0]) == int(m.group(1)):
        v, li = defs["WP_MEMORY_LIMIT"]
        F("CONFIG-MEMORY", "Critical", "Configuration", f"WP_MEMORY_LIMIT {v} exhausted",
          f"PHP hit the {v} limit set at wp-config.php line {li} while running {m.group(2).split('/wp-content/')[-1]}:{m.group(3)}", f"wp-config.php:{li}")
        continue
    m = re.search(r"PHP Fatal error:.* in (\S+?)(?::| on line )(\d+)", ln)
    if m:
        s = re.search(r"/plugins/([\w-]+)/", m.group(1))
        if s and s.group(1) not in active:
            F("LOG-HISTORICAL", "Info", "Log", f"Older fatal from {s.group(1)}, which is no longer active", ln[:200], f"wp-content/debug.log:{i}")
        elif s:
            F("FATAL", "Critical", "Fatal error", f"Fatal error in {s.group(1)}", ln[:200], f"wp-content/debug.log:{i}")
if defs.get("WP_CACHE", ("false",))[0] == "true" and rd("wp-content/advanced-cache.php") is None:
    F("CONFIG-WP-CACHE", "Warning", "Configuration", "WP_CACHE is true but wp-content/advanced-cache.php is missing",
      f"wp-config.php line {defs['WP_CACHE'][1]}; responses carry no cache header", f"wp-config.php:{defs['WP_CACHE'][1]}")
slow = rd("mysql-slow.log") or ""
agg = {}
for m in re.finditer(r"# Query_time: ([\d.]+)[^\n]*\n(?:SET timestamp=\d+;\n)?([^\n#]+)", slow):
    t = re.search(r"(?:FROM|INTO|UPDATE)\s+`?(wp_\w+)", m.group(2))
    if t:
        agg.setdefault(t.group(1), []).append(float(m.group(1)))
if agg:
    tbl = max(agg, key=lambda k: (max(agg[k]), sum(agg[k])))
    cands = [p.get("name") for p in plist if tbl.startswith("wp_" + p.get("name").split("-")[0])]
    owner = cands[0] if cands else "core or unknown"
    F("SLOW-QUERY", "Warning", "Performance", f"Slow query on {tbl} attributed to {owner}",
      f"worst Query_time {max(agg[tbl]):.6f}s, {len(agg[tbl])} slow entries, total {sum(agg[tbl]):.6f}s", "mysql-slow.log")
try:
    qm = json.loads(rd("qm-db.json") or "null")
except ValueError:
    qm = None
if qm:
    top = max(qm["queries"], key=lambda q: q["time"])
    if top["time"] >= 0.5:
        F("SLOW-QUERY-QM", "Warning", "Performance", f"Slow query from {top['component'].split(': ')[-1]}",
          f"query time {top['time']}s: {top['sql'][:80]}", top["location"])
tm = rd("timings.csv")
if tm:
    rows = list(csv.DictReader(tm.splitlines()))
    st = {ph: {r["cache"] for r in rows if r["phase"] == ph} for ph in ("before", "after")}
    if st["before"] != st["after"] or len(st["before"]) != 1:
        F("PERF-SPEEDUP-REFUSED", "Info", "Performance", "Before/after timings not comparable: cache state differs",
          f"before cache {sorted(st['before'])}, after cache {sorted(st['after'])}; no speedup claimed", "timings.csv")
    else:
        med = {ph: statistics.median(float(r["ttfb_ms"]) for r in rows if r["phase"] == ph) for ph in ("before", "after")}
        F("PERF-SPEEDUP", "Info", "Performance", f"Median TTFB {med['before']:.0f} ms -> {med['after']:.0f} ms: {med['before'] / med['after']:.2f}x faster",
          f"same cache state ({sorted(st['before'])[0]}), n={len(rows) // 2} per phase", "timings.csv")
if not tm and not slow and not qm:
    F("PERF-RUNTIME-SKIP", "Info", "Performance", "No runtime timing evidence in bundle; runtime profiling needs WP-CLI profile on a disposable site", "", "")
print(json.dumps(out or [{"id": "DIAG-CLEAN", "severity": "Info", "category": "Diagnostics", "title": "No issues found"}]))
