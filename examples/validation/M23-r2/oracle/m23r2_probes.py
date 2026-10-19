#!/usr/bin/env python3
"""M23 r2 probes on S1-S5 edge cases (Grok self-validation). Kinds: doc = expectation from the text of
wp-trace-diagnosis.md at 0ff2641; claim = a builder REWORK.md claim the doc does not state (scored, reported
separately); obs = doc silent, recorded only, never scored.
Usage: m23r2_probes.py PYTHON TOOL OUTDIR"""
import copy, json, os, subprocess, sys, tempfile
PY, TOOL, OUT = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)
BASE = {"schema": "solaris.wp-trace/1", "site": "probe-site", "environment": "production", "source": "Grok M23 r2 probe, synthetic",
        "env": {"php": "8.3.0", "wp": "6.6.2", "host": "probe"},
        "measurement": {"tool": "probe", "warm_cache": False, "runs_per_url": 5, "concurrency": 1},
        "wp_config": {"WP_DEBUG": False, "WP_CACHE": False}, "dropins": [], "active_plugins": ["alpha", "beta", "gamma"],
        "autoload_bytes": 1000, "autoload_top": [], "system_cron": True, "requests": [], "php_errors": [], "bisect": []}
P = "/srv/www/wp-content/plugins/"
def B(**kw):
    b = copy.deepcopy(BASE)
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(b.get(k), dict): b[k].update(v)
        else: b[k] = v
    return b
def req(rid="r1", url="/", total=500.0, queries=(), peak=None):
    r = {"id": rid, "url": url, "total_ms": total, "queries": list(queries), "hooks": []}
    if peak is not None: r["peak_memory_mb"] = peak
    return r
def q(sql="SELECT * FROM wp_posts WHERE ID = 1", ms=1.0, caller=None, comp=None, sf=None, sl=None):
    d = {"sql": sql, "ms": ms}
    for k, v in (("caller", caller), ("component", comp), ("source_file", sf), ("source_line", sl)):
        if v is not None: d[k] = v
    return d
def run(args, files, setup=None):
    d = tempfile.mkdtemp(prefix="m23r2p-", dir="/tmp"); DIRS.append(d)
    for name, content in files.items():
        p = os.path.join(d, name); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f: f.write(content if isinstance(content, str) else json.dumps(content))
    if setup: setup(d)
    cp = subprocess.run([PY, TOOL] + [a.format(d=d) for a in args], capture_output=True, text=True, timeout=60, cwd=d,
                        env={"PATH": "/usr/bin:/bin", "HOME": d, "PYTHONDONTWRITEBYTECODE": "1"})
    try: rep = json.loads(cp.stdout)
    except ValueError: rep = None
    return cp, rep, d
tb = lambda cp: "Traceback" in cp.stderr
def diag(b, extra=()):
    cp, rep, _ = run(["diagnose", "{d}/b.json", "--json", *extra], {"b.json": b}); return cp, rep
def F(rep, code): return [f for f in (rep or {}).get("findings", []) if f["code"] == code]
results = []
DIRS = []
def probe(pid, kind, ok, detail):
    res = "OBS" if kind == "obs" else ("PASS" if ok else "FAIL")
    results.append({"id": pid, "kind": kind, "result": res, "detail": detail})
    print(f"{pid:4} {kind:5} {res}  {json.dumps(detail)[:300]}")
def mem(nbytes=33554432, plug="alpha"):
    return f"[18-Oct-2026 10:00:00 UTC] PHP Fatal error:  Allowed memory size of {nbytes} bytes exhausted (tried to allocate 20480 bytes) in {P}{plug}/r.php on line 3"
def M(wml, nbytes=33554432, extra_errors=()):
    cfg = {} if wml is None else {"WP_MEMORY_LIMIT": wml}
    cp, r = diag(B(wp_config=cfg, php_errors=[mem(nbytes)] + list(extra_errors)))
    f = F(r, "CONFIG_MEMORY_LIMIT")
    return cp, f, (json.dumps(f[0]) if f else "")
# ---- S1
cp, f, s = M("32M"); probe("A01", "doc", len(f) == 1 and f[0]["components"] == ["core"] and "WP_MEMORY_LIMIT" in s and "alpha" not in f[0]["components"], {"f": f})
cp, f, s = M("1G"); probe("A02", "doc", len(f) == 1 and f[0]["components"] == ["core"] and "memory_limit" in f[0]["detail"] and "above" in f[0]["detail"].lower() + " above" and "WP_MEMORY_LIMIT=1G" in f[0]["evidence"], {"detail": f and f[0]["detail"], "ev": f and f[0]["evidence"]})
cp, f, s = M("1024M", 1073741824); probe("A03", "doc", len(f) == 1 and "configured" in f[0]["detail"] and "memory_limit is lower" not in f[0]["detail"], {"detail": f and f[0]["detail"], "note": "1024M equals 1 GiB died-at"})
cp, f, s = M("1G", 1073741824); probe("A03b", "doc", len(f) == 1 and "memory_limit is lower" not in f[0]["detail"], {"detail": f and f[0]["detail"]})
cp, f, s = M("32m"); probe("A04", "doc", len(f) == 1 and "configured" in f[0]["detail"], {"detail": f and f[0]["detail"], "note": "lowercase m, PHP shorthand is case-insensitive"})
cp, f, s = M("16M"); probe("A05", "doc", len(f) == 1 and f[0]["components"] == ["core"] and "memory_limit is lower" not in f[0]["detail"], {"detail": f and f[0]["detail"], "note": "died above the configured limit: must not claim the PHP cap is lower"})
cp, f, s = M(None); probe("A06", "doc", len(f) == 1 and "not in the bundle" in f[0]["detail"] and f[0]["components"] == ["core"], {"detail": f and f[0]["detail"]})
cp, f, s = M("-1"); probe("A07", "obs", True, {"rc": cp.returncode, "detail": f and f[0]["detail"], "note": "-1 is PHP's unlimited"})
cp, f, s = M(-1); probe("A07b", "obs", True, {"rc": cp.returncode, "tb": tb(cp), "detail": f and f[0]["detail"], "note": "JSON int -1"})
cp, f, s = M("256MB"); probe("A08", "obs", True, {"rc": cp.returncode, "detail": f and f[0]["detail"]})
cp, f, s = M(33554432); probe("A09", "obs", True, {"rc": cp.returncode, "detail": f and f[0]["detail"], "note": "JSON int bytes"})
cp, f, s = M("abc"); probe("A10", "doc", cp.returncode == 1 and len(f) == 1 and not tb(cp), {"rc": cp.returncode, "detail": f and f[0]["detail"], "note": "not a size: still a finding, no crash"})
cp, f, s = M("32M", extra_errors=[mem(33554432, "beta")]); probe("A11", "doc", len(f) == 1 and f[0]["components"] == ["core"], {"f": f, "note": "two plugins in two lines: one core finding"})
cp, r = diag(B(wp_config={"WP_MEMORY_LIMIT": "100M"}, requests=[req(peak=95.0)])); f = F(r, "CONFIG_MEMORY_LIMIT")
probe("A12", "doc", len(f) == 1 and f[0]["components"] == ["core"], {"f": f, "note": "peak-90% path: the doc says the component is core"})
cp, f, s = M("32M"); probe("A13", "doc", any("alpha" in e for e in f[0]["evidence"]) if f else False, {"ev": f and f[0]["evidence"], "note": "line's file still reported as where memory ran out"})
# ---- S2
def S(queries, extra=(), text=False):
    b = B(requests=[req(queries=queries)])
    if text:
        cp, _, _ = run(["diagnose", "{d}/b.json"], {"b.json": b}); return cp, None
    return diag(b, extra)
SQ = "SELECT * FROM wp_acme_index WHERE term LIKE '%x%'"
cp, r = S([q(SQ, 200, sf="mysql-slow.log", sl=1204)]); f = F(r, "SLOW_QUERY")
probe("B01", "doc", len(f) == 1 and any("mysql-slow.log:1204" in e for e in f[0]["evidence"]) and "mysql-slow.log:1204" in f[0].get("sources", []), {"f": f})
probe("B02", "doc", len(f) == 1 and f[0]["components"] == ["unknown"] and "not tied to a plugin" in f[0]["detail"] and not any(c.startswith("plugin:") for c in f[0]["components"]), {"detail": f and f[0]["detail"], "comp": f and f[0]["components"], "note": "wp_acme_ table in SQL must not become plugin:acme"})
for pid, order in (("B03", [q(SQ, 200, sf="A.log", sl=10), q(SQ, 60, sf="B.log", sl=20)]), ("B03b", [q(SQ, 60, sf="B.log", sl=20), q(SQ, 200, sf="A.log", sl=10)])):
    cp, r = S(order); f = F(r, "SLOW_QUERY"); src = [e for e in (f[0]["evidence"] if f else []) if e.startswith("source ")]
    probe(pid, "doc", bool(src) and src[0] == "source A.log:10", {"src": src, "note": "evidence leads with the slowest run"})
cp, r = S([q(SQ, 100 + i, sf="s.log", sl=i + 1) for i in range(25)]); f = F(r, "SLOW_QUERY")
probe("B04", "doc", len(f) == 1 and len(f[0].get("sources", [])) == 20, {"n": f and len(f[0].get("sources", []))})
cp, r = S([q(SQ, 200, sf="mysql-slow.log")]); f = F(r, "SLOW_QUERY")
probe("B05", "doc", cp.returncode == 1 and f and "mysql-slow.log" in f[0].get("sources", []), {"rc": cp.returncode, "f": f, "note": "source_file without a line is allowed (both optional)"})
inv = {"B06_line_no_file": q(SQ, 200, sl=5), "B07_newline": q(SQ, 200, sf="a\nb.log", sl=1), "B08_257": q(SQ, 200, sf="x" * 257, sl=1),
       "B09_line0": q(SQ, 200, sf="a.log", sl=0), "B10_line_1e9p1": q(SQ, 200, sf="a.log", sl=1000000001), "B11_line_str": q(SQ, 200, sf="a.log", sl="12"),
       "B12_empty_file": q(SQ, 200, sf="", sl=1), "B13_file_num": q(SQ, 200, sf=5, sl=1), "B14_line_nan_bool": q(SQ, 200, sf="a.log", sl=True)}
for k, qq in inv.items():
    cp, r = S([qq]); kind = "doc" if k.startswith("B06") else "claim"
    probe(k.split("_")[0], kind, cp.returncode == 2 and not tb(cp) and cp.stdout.strip() == "", {"case": k, "rc": cp.returncode, "tb": tb(cp), "stderr": cp.stderr.strip()[-120:]})
for k, qq in {"B15_256": q(SQ, 200, sf="x" * 256, sl=1), "B16_line_1e9": q(SQ, 200, sf="a.log", sl=1000000000), "B17_line_1": q(SQ, 200, sf="a.log", sl=1)}.items():
    cp, r = S([qq]); probe(k.split("_")[0], "claim", cp.returncode == 1 and not tb(cp), {"case": k, "rc": cp.returncode})
cp, r = S([q(SQ, 200, sf="a.log", sl=12.7)]); probe("B18", "obs", True, {"rc": cp.returncode, "sources": [f.get("sources") for f in F(r, "SLOW_QUERY")], "note": "non-integer line"})
cp, r = S([q(SQ, 200, caller="acme_find()", comp="unknown")]); probe("B19", "obs", True, {"detail": [f["detail"] for f in F(r, "SLOW_QUERY")], "note": "unknown component with a caller"})
cp, r = S([q("SELECT meta FROM wp_postmeta WHERE post_id = %d" % i, 2, caller="loop()", comp="plugin:beta", sf="qm", sl=40) for i in range(12)]); f = F(r, "REPEATED_QUERY")
probe("B20", "doc", len(f) == 1 and f[0].get("sources") == ["qm:40"] and f[0]["components"] == ["plugin:beta"], {"f": f, "note": "REPEATED_QUERY keeps source"})
cp, _ = S([q(SQ, 200 + i, sf="s.log", sl=i + 1) for i in range(7)], text=True)
probe("B21", "claim", "sources:" in cp.stdout and "and 2 more" in cp.stdout, {"out": [l for l in cp.stdout.splitlines() if "sources" in l]})
cp, r = S([q(SQ, 200, sf="a\tb.log", sl=1)]); probe("B22", "claim", cp.returncode == 2 and not tb(cp), {"rc": cp.returncode})
cp, r = S([q(SQ, 200, sf="mysql-slow.log", sl=1204, comp="plugin:alpha", caller="a()")]); f = F(r, "SLOW_QUERY")
probe("B23", "doc", f and f[0]["components"] == ["plugin:alpha"] and "not tied" not in f[0]["detail"], {"f": f, "note": "QM attribution still used when present"})
# ---- S4 / S5
cache = B(wp_config={"WP_CACHE": True})
cp, rep, d = run(["diagnose", "{d}/b.json", "--json", "--out", "{d}/o.json"], {"b.json": cache}); oj = json.load(open(d + "/o.json")) if os.path.exists(d + "/o.json") else None
probe("C01", "doc", rep is not None and oj == rep, {"rc": cp.returncode, "stdout_json": rep is not None})
cp, rep, d = run(["diagnose", "{d}/b.json", "--out", "{d}/o.json"], {"b.json": cache}); oj = json.load(open(d + "/o.json")) if os.path.exists(d + "/o.json") else None
probe("C02", "doc", rep is None and oj is not None and "CONFIG_CACHE_DROPIN_MISSING" in cp.stdout, {"rc": cp.returncode, "head": cp.stdout[:80]})
smp = lambda vals: [req("s%d" % i, "/", float(v)) for i, v in enumerate(vals)]
cb, ca = B(requests=smp([800, 810, 790, 805, 795])), B(requests=smp([400, 410, 390, 405, 395]))
cp, rep, d = run(["compare", "{d}/b.json", "{d}/a.json", "--json", "--out", "{d}/o.json"], {"b.json": cb, "a.json": ca}); oj = json.load(open(d + "/o.json")) if os.path.exists(d + "/o.json") else None
probe("C03", "doc", cp.returncode == 0 and rep is not None and oj == rep and rep.get("speedup_claimed") is True, {"rc": cp.returncode, "stdout_json": rep is not None, "file": oj is not None})
cp, rep, d = run(["compare", "{d}/b.json", "{d}/a.json", "--out", "{d}/o.json"], {"b.json": cb, "a.json": ca}); oj = json.load(open(d + "/o.json")) if os.path.exists(d + "/o.json") else None
probe("C04", "doc", rep is None and oj is not None and "comparable" in cp.stdout, {"rc": cp.returncode, "head": cp.stdout[:60]})
cp, rep, d = run(["compare", "{d}/b.json", "{d}/a.json", "--out", "{d}/a.json"], {"b.json": cb, "a.json": ca})
probe("C05", "doc", cp.returncode == 2 and json.load(open(d + "/a.json")) == ca and not tb(cp), {"rc": cp.returncode})
cp, rep, d = run(["compare", "{d}/b.json", "{d}/a.json", "--json", "--out", "{d}/o.json"], {"b.json": cb, "a.json": B(site="x", requests=smp([400] * 5))})
probe("C06", "doc", cp.returncode == 3 and rep is not None and os.path.exists(d + "/o.json"), {"rc": cp.returncode, "file": os.path.exists(d + "/o.json"), "note": "not comparable is a valid run: report written"})
def outcase(pid, kind, setup, target, check, note):
    cp, rep, d = run(["diagnose", "{d}/b.json", "--json", "--out", target], {"b.json": cache, "keep.json": "KEEP"}, setup)
    probe(pid, kind, check(cp, d), {"rc": cp.returncode, "tb": tb(cp), "stderr": cp.stderr.strip()[-100:], "note": note})
outcase("D01", "doc", lambda d: os.mkdir(d + "/dir"), "{d}/dir", lambda cp, d: cp.returncode == 2 and os.listdir(d + "/dir") == [] and not tb(cp), "--out is a folder")
outcase("D02", "doc", lambda d: os.symlink(d + "/keep.json", d + "/ln.json"), "{d}/ln.json", lambda cp, d: cp.returncode == 2 and open(d + "/keep.json").read() == "KEEP" and os.path.islink(d + "/ln.json"), "symlink to another file")
outcase("D03", "doc", lambda d: os.symlink(d + "/nowhere.json", d + "/dang.json"), "{d}/dang.json", lambda cp, d: cp.returncode == 2 and not os.path.exists(d + "/nowhere.json"), "dangling symlink")
outcase("D04", "doc", None, "{d}/missing/o.json", lambda cp, d: cp.returncode == 2 and not tb(cp), "folder missing")
outcase("D05", "doc", lambda d: os.link(d + "/b.json", d + "/hl.json"), "{d}/hl.json", lambda cp, d: cp.returncode == 2 and json.load(open(d + "/b.json")) == cache, "hardlink to input")
outcase("D06", "doc", lambda d: os.symlink(d + "/b.json", d + "/lb.json"), "{d}/lb.json", lambda cp, d: cp.returncode == 2 and json.load(open(d + "/b.json")) == cache, "symlink to input")
outcase("D07", "doc", lambda d: (os.mkdir(d + "/real"), os.symlink(d + "/real", d + "/ld")), "{d}/ld/../b.json", lambda cp, d: json.load(open(d + "/b.json")) == cache, "input reached through a symlinked folder and ..: input must stay intact")
outcase("D08", "obs", lambda d: (os.mkdir(d + "/real"), os.symlink(d + "/real", d + "/ld")), "{d}/ld/o.json", lambda cp, d: True, "parent folder is a symlink (doc silent)")
outcase("D09", "doc", lambda d: (os.mkdir(d + "/real"), os.symlink(d + "/b.json", d + "/real/x.json"), os.symlink(d + "/real", d + "/ld")), "{d}/ld/x.json", lambda cp, d: cp.returncode == 2 and json.load(open(d + "/b.json")) == cache, "symlinked folder holding a symlink to the input")
cp, r = diag(B(requests=[req(queries=[q(SQ, 200, caller="x()", comp="unknown")])]))
probe("D10", "doc", cp.returncode != 2, {"rc": cp.returncode, "note": "component unknown accepted"})
RED = "[18-Oct-2026 10:00:00 UTC] PHP Fatal error:  Cannot redeclare f_x() (previously declared in %s:4) in %s on line 9"
for pid, a, c in (("D11", "/srv/www/lib/compat.php", P + "beta/b.php"), ("D11b", P + "beta/b.php", "/srv/www/lib/compat.php")):
    cp, r = diag(B(php_errors=[RED % (a, c)])); f = F(r, "PLUGIN_FATAL")
    probe(pid, "doc", len(f) == 1 and f[0]["components"] == ["plugin:beta"] and "outside wp-content" in f[0]["detail"] and not F(r, "PLUGIN_CONFLICT"), {"codes": [x["code"] for x in r["findings"]] if r else None, "f": f})
cp, r = diag(B(php_errors=[RED % ("/srv/www/lib/a.php", "/srv/www/lib/b.php")])); probe("D12", "obs", True, {"rc": cp.returncode, "findings": r and r["findings"], "note": "both declarers outside wp-content"})
cp, r = diag(B(php_errors=[RED % ("/srv/www/wp-content/themes/t1/functions.php", "/srv/www/lib/b.php")])); f = F(r, "PLUGIN_FATAL")
probe("D13", "doc", len(f) == 1 and f[0]["components"] == ["theme:t1"], {"f": f, "note": "theme vs outside"})
json.dump(results, open(os.path.join(OUT, "probes.json"), "w"), indent=1)
import shutil
for _d in DIRS: shutil.rmtree(_d, ignore_errors=True)
sc = [r for r in results if r["kind"] != "obs"]
print("TOTAL %d/%d scored (doc %d/%d, claim %d/%d), obs %d" % (sum(r["result"] == "PASS" for r in sc), len(sc),
      sum(r["result"] == "PASS" for r in sc if r["kind"] == "doc"), sum(r["kind"] == "doc" for r in sc),
      sum(r["result"] == "PASS" for r in sc if r["kind"] == "claim"), sum(r["kind"] == "claim" for r in sc), len(results) - len(sc)))
