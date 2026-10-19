#!/usr/bin/env python3
"""M23 r1 native-schema probes (Grok self-validation). Every expectation is taken from the text of
wp-trace-diagnosis.md at d6be00e (codes table, input rules, speedup rules, --out rules), not from the code.
Usage: m23r1_probes.py PYTHON TOOL OUTDIR   -> prints one line per probe and writes OUTDIR/probes.json"""
import copy, json, os, subprocess, sys, tempfile

PY, TOOL, OUT = sys.argv[1:4]
os.makedirs(OUT, exist_ok=True)
SECRETS = ["probe-not-a-secret-db", "probe-not-a-secret-auth", "probe-not-a-secret-token", "probe-not-a-secret-smtp"]
BASE = {"schema": "solaris.wp-trace/1", "site": "probe-site", "environment": "production", "source": "Grok M23 r1 probe, synthetic",
        "env": {"php": "8.3.0", "wp": "6.6.2", "host": "probe"},
        "measurement": {"tool": "probe", "warm_cache": False, "runs_per_url": 5, "concurrency": 1},
        "wp_config": {"WP_DEBUG": False, "WP_CACHE": False}, "dropins": [], "active_plugins": ["alpha", "beta", "gamma"],
        "autoload_bytes": 1000, "autoload_top": [], "system_cron": True, "requests": [], "php_errors": [], "bisect": []}
P = "/srv/www/wp-content/plugins/"
RED = "[18-Oct-2026 10:00:00 UTC] PHP Fatal error:  Cannot redeclare f_x() (previously declared in %s:4) in %s on line 9"


def B(**kw):
    b = copy.deepcopy(BASE)
    for k, v in kw.items():
        if isinstance(v, dict) and isinstance(b.get(k), dict):
            b[k].update(v)
        else:
            b[k] = v
    return b


def req(rid="r1", url="/", total=100.0, queries=(), hooks=(), peak=None):
    r = {"id": rid, "url": url, "total_ms": total, "queries": list(queries), "hooks": list(hooks)}
    if peak is not None:
        r["peak_memory_mb"] = peak
    return r


def q(sql="SELECT 1", ms=1.0, caller="c()", comp="core"):
    return {"sql": sql, "ms": ms, "caller": caller, "component": comp}


def run(args, files):
    d = tempfile.mkdtemp(prefix="m23r1-", dir="/tmp")
    paths = {}
    for name, content in files.items():
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(p, mode) as f:
            f.write(content if isinstance(content, (str, bytes)) else json.dumps(content))
        paths[name] = p
    argv = [a.format(d=d, **{k.replace(".", "_").replace("/", "_"): v for k, v in paths.items()}) for a in args]
    cp = subprocess.run([PY, TOOL] + argv, capture_output=True, text=True, timeout=60, cwd=d,
                        env={"PATH": "/usr/bin:/bin", "HOME": d, "PYTHONDONTWRITEBYTECODE": "1"})
    try:
        rep = json.loads(cp.stdout)
    except ValueError:
        rep = None
    return cp, rep, d


def codes(rep):
    return [f["code"] for f in (rep or {}).get("findings", [])]


def comps(rep, code):
    return [sorted(f["components"]) for f in (rep or {}).get("findings", []) if f["code"] == code]


results = []


def probe(pid, ok, detail):
    results.append({"id": pid, "result": "PASS" if ok else "FAIL", "detail": detail})
    print(f"{pid:4} {'PASS' if ok else 'FAIL'}  {json.dumps(detail)[:260]}")


def diag(b, extra=()):
    cp, rep, d = run(["diagnose", "{d}/b.json", "--json", *extra], {"b.json": b})
    return cp, rep


def tb(cp):
    return "Traceback" in cp.stderr or "Traceback" in cp.stdout

# ---- detection rules (codes table)
cp, r = diag(B(php_errors=[RED % (P + "alpha/a.php", P + "beta/b.php")]))
probe("N01", cp.returncode == 1 and comps(r, "PLUGIN_CONFLICT") == [["plugin:alpha", "plugin:beta"]], {"rc": cp.returncode, "codes": codes(r)})
cp, r = diag(B(php_errors=[RED % (P + "alpha/a.php", P + "alpha/b.php")]))
probe("N02", "PLUGIN_FATAL" in codes(r) and "PLUGIN_CONFLICT" not in codes(r), {"codes": codes(r)})
cls = "[18-Oct-2026 10:00:00 UTC] PHP Fatal error:  Cannot declare class Acme_Util, because the name is already in use in " + P + "beta/inc/u.php on line 3"
cp, r = diag(B(php_errors=[cls]))
probe("N03", any("plugin:beta" in c for c in comps(r, "PLUGIN_CONFLICT")), {"codes": codes(r), "c": comps(r, "PLUGIN_CONFLICT")})
bis_pair = [{"plugins": ["alpha", "beta", "gamma"], "result": "fail"}, {"plugins": ["alpha", "gamma"], "result": "ok"},
            {"plugins": ["beta", "gamma"], "result": "ok"}, {"plugins": ["alpha", "beta"], "result": "fail"}]
cp, r = diag(B(bisect=bis_pair))
probe("N04", comps(r, "PLUGIN_CONFLICT") == [["plugin:alpha", "plugin:beta"]] or comps(r, "PLUGIN_CONFLICT") == [["alpha", "beta"]], {"codes": codes(r), "c": comps(r, "PLUGIN_CONFLICT")})
bis_one = [{"plugins": ["alpha", "beta", "gamma"], "result": "fail"}, {"plugins": ["alpha", "beta"], "result": "ok"},
           {"plugins": ["gamma"], "result": "fail"}, {"plugins": ["alpha"], "result": "ok"}]
cp, r = diag(B(bisect=bis_one))
probe("N05", "PLUGIN_FAULT" in codes(r) and "gamma" in json.dumps(comps(r, "PLUGIN_FAULT")) and "PLUGIN_CONFLICT" not in codes(r), {"codes": codes(r), "c": comps(r, "PLUGIN_FAULT")})
bis_amb = [{"plugins": ["alpha", "beta", "gamma"], "result": "fail"}, {"plugins": ["alpha"], "result": "ok"}]
cp, r = diag(B(bisect=bis_amb))
probe("N06", "PLUGIN_FAILURE_UNLOCALIZED" in codes(r) and not {"PLUGIN_CONFLICT", "PLUGIN_FAULT"} & set(codes(r)), {"codes": codes(r)})
cp, r = diag(B(active_plugins=["acme-search", "acme-search-legacy"], php_errors=[RED % (P + "acme-search-legacy/l.php", P + "acme-search/s.php")]))
probe("N07", comps(r, "PLUGIN_CONFLICT") == [["plugin:acme-search", "plugin:acme-search-legacy"]], {"c": comps(r, "PLUGIN_CONFLICT")})
cp, r = diag(B(php_errors=[RED % ("/srv/www/wp-content/mu-plugins/ops/o.php", P + "beta/b.php")]))
probe("N08", comps(r, "PLUGIN_CONFLICT") == [["mu-plugin:ops", "plugin:beta"]], {"c": comps(r, "PLUGIN_CONFLICT")})
cp, r = diag(B(php_errors=[RED % ("/srv/www/wp-content/themes/solaris-child/functions.php", P + "beta/b.php")]))
probe("N09", comps(r, "PLUGIN_CONFLICT") == [["plugin:beta", "theme:solaris-child"]], {"c": comps(r, "PLUGIN_CONFLICT")})
_, r1 = diag(B(requests=[req(queries=[q("SELECT * FROM wp_x", 50.0, comp="plugin:alpha")])]))
_, r2 = diag(B(requests=[req(queries=[q("SELECT * FROM wp_x", 49.99, comp="plugin:alpha")])]))
probe("N10", "SLOW_QUERY" in codes(r1) and "SLOW_QUERY" not in codes(r2), {"at50": codes(r1), "at49.99": codes(r2)})
mk = lambda n, caller="c()": [q("SELECT v FROM wp_postmeta WHERE post_id = %d" % i, 1.0, caller, "plugin:alpha") for i in range(n)]
_, r1 = diag(B(requests=[req(queries=mk(10))]))
_, r2 = diag(B(requests=[req(queries=mk(9))]))
_, r3 = diag(B(requests=[req(queries=mk(5, "a()") + mk(5, "b()"))]))
probe("N11", "REPEATED_QUERY" in codes(r1) and "REPEATED_QUERY" not in codes(r2) and "REPEATED_QUERY" not in codes(r3), {"10": codes(r1), "9": codes(r2), "5+5 callers": codes(r3)})
inq = [q("SELECT * FROM wp_posts WHERE ID IN (%s)" % ",".join(str(j) for j in range(i % 3 + 1)), 1.0, "c()", "plugin:alpha") for i in range(10)]
_, r = diag(B(requests=[req(queries=inq)]))
probe("N12", "REPEATED_QUERY" in codes(r), {"codes": codes(r)})
_, r1 = diag(B(requests=[req(hooks=[{"hook": "init", "callback": "a_init", "component": "plugin:alpha", "ms": 100.0}])]))
_, r2 = diag(B(requests=[req(hooks=[{"hook": "init", "callback": "a_init", "component": "plugin:alpha", "ms": 99.9}])]))
probe("N13", "SLOW_HOOK_CALLBACK" in codes(r1) and "SLOW_HOOK_CALLBACK" not in codes(r2), {"100": codes(r1), "99.9": codes(r2)})
cases = {"prod_absent": B(wp_config={"WP_DEBUG": True}), "prod_true": B(wp_config={"WP_DEBUG": True, "WP_DEBUG_DISPLAY": True}),
         "prod_false": B(wp_config={"WP_DEBUG": True, "WP_DEBUG_DISPLAY": False}), "staging_absent": B(environment="staging", wp_config={"WP_DEBUG": True})}
got = {k: "CONFIG_DEBUG_DISPLAY" in codes(diag(v)[1]) for k, v in cases.items()}
probe("N14", got == {"prod_absent": True, "prod_true": True, "prod_false": False, "staging_absent": False}, got)
got = {"prod": "CONFIG_SAVEQUERIES" in codes(diag(B(wp_config={"SAVEQUERIES": True}))[1]),
       "staging": "CONFIG_SAVEQUERIES" in codes(diag(B(environment="staging", wp_config={"SAVEQUERIES": True}))[1])}
probe("N15", got == {"prod": True, "staging": False}, got)
got = {"90pct": "CONFIG_MEMORY_LIMIT" in codes(diag(B(wp_config={"WP_MEMORY_LIMIT": "100M"}, requests=[req(peak=90.0)]))[1]),
       "89pct": "CONFIG_MEMORY_LIMIT" in codes(diag(B(wp_config={"WP_MEMORY_LIMIT": "100M"}, requests=[req(peak=89.0)]))[1])}
probe("N16", got == {"90pct": True, "89pct": False}, got)
got = {"on_nodropin": codes(diag(B(wp_config={"WP_CACHE": True}))[1]),
       "off_dropin": codes(diag(B(dropins=["advanced-cache.php"]))[1]),
       "absent_dropin": codes(diag(B(wp_config={"WP_DEBUG": False}, dropins=["advanced-cache.php"]) | {"wp_config": {"WP_DEBUG": False}})[1])}
probe("N17", "CONFIG_CACHE_DROPIN_MISSING" in got["on_nodropin"] and "CONFIG_CACHE_DISABLED" in got["off_dropin"] and "CONFIG_CACHE_DISABLED" in got["absent_dropin"], got)
_, rf = diag(B(wp_config={"DISABLE_WP_CRON": True}, system_cron=False))
_, rn = diag(B(wp_config={"DISABLE_WP_CRON": True}, system_cron=None))
probe("N18", "CONFIG_CRON_NOT_RUNNING" in codes(rf) and "CONFIG_CRON_NOT_RUNNING" not in codes(rn) and any("cron" in n.lower() for n in (rn or {}).get("notes", [])),
      {"false": codes(rf), "null": codes(rn), "null_notes": (rn or {}).get("notes")})
got = {"800001": "CONFIG_AUTOLOAD_BLOAT" in codes(diag(B(autoload_bytes=800001, autoload_top=[{"option": "big", "bytes": 700000}]))[1]),
       "800000": "CONFIG_AUTOLOAD_BLOAT" in codes(diag(B(autoload_bytes=800000))[1])}
probe("N19", got == {"800001": True, "800000": False}, got)
cp, r = diag(B())
probe("N20", cp.returncode == 0 and codes(r) == [], {"rc": cp.returncode, "codes": codes(r)})
mem = "[18-Oct-2026 10:00:00 UTC] PHP Fatal error:  Allowed memory size of 33554432 bytes exhausted (tried to allocate 20480 bytes) in " + P + "alpha/r.php on line 3"
_, r = diag(B(wp_config={"WP_MEMORY_LIMIT": "32M"}, php_errors=[mem]))
f = [x for x in (r or {}).get("findings", []) if x["code"] == "CONFIG_MEMORY_LIMIT"]
probe("N21", bool(f) and "core" in f[0]["components"], {"finding": f, "note": "config-rooted fault: is core/config named as a component, or only the allocating plugin"})
_, r = diag(B(wp_config={"WP_MEMORY_LIMIT": "256M"}, php_errors=[mem]))
probe("N22", "256" in json.dumps(r) and "32" in json.dumps(r), {"note": "configured 256M but PHP died at 32 MiB (php memory_limit cap); is the mismatch surfaced", "findings": (r or {}).get("findings")})

# ---- strict input (exit 2, nothing written)
def strict(pid, content, name="b.json", extra_files=None, args=None):
    files = {name: content}
    files.update(extra_files or {})
    cp, rep, d = run(args or ["diagnose", "{d}/" + name, "--json", "--out", "{d}/out.json"], files)
    ok = cp.returncode == 2 and not tb(cp) and not os.path.exists(os.path.join(d, "out.json"))
    probe(pid, ok, {"rc": cp.returncode, "traceback": tb(cp), "out_written": os.path.exists(os.path.join(d, "out.json")), "stderr": cp.stderr[-160:]})
good = json.dumps(B(requests=[req()]))
strict("S01", json.dumps(B(extra_field=1)))
strict("S02", good[:-1] + ', "site": "dup"}')
strict("S03", good.replace('"total_ms": 100.0', '"total_ms": NaN'))
strict("S04", good.replace('"total_ms": 100.0', '"total_ms": Infinity'))
strict("S05", good.replace('"total_ms": 100.0', '"total_ms": true'))
strict("S06", "[" * 5000 + "]" * 5000)
strict("S07", json.dumps(B(requests=[req(queries=[q(comp="Plugin: alpha")])])))
strict("S08", "")
strict("S09", b"\xff\xfe\x00garbage")
strict("S10", good, args=["diagnose", "{d}/missing.json", "--json", "--out", "{d}/out.json"])
strict("S11", json.dumps(B(environment="prod")))
strict("S12", json.dumps(B(schema="solaris.wp-trace/2")))
strict("S13", json.dumps(B(requests=[req(queries=[q(ms=-5.0)])])))
strict("S14", json.dumps(B(env={"php": "8.3", "wp": "6.6", "host": "h", "os": "linux"})))
# symlinked bundle
d = tempfile.mkdtemp(prefix="m23r1-", dir="/tmp"); open(os.path.join(d, "real.json"), "w").write(good); os.symlink(os.path.join(d, "real.json"), os.path.join(d, "link.json"))
cp = subprocess.run([PY, TOOL, "diagnose", os.path.join(d, "link.json"), "--json"], capture_output=True, text=True, timeout=60)
probe("S15", cp.returncode == 2 and not tb(cp), {"rc": cp.returncode, "stderr": cp.stderr[-160:]})

# ---- secrets never echoed
sec = B(wp_config={"DB_PASSWORD": SECRETS[0], "AUTH_KEY": SECRETS[1], "MY_API_TOKEN": SECRETS[2], "SMTP_PASS": SECRETS[3], "WP_DEBUG": True},
        requests=[req(queries=[q("SELECT * FROM wp_users WHERE user_pass = '%s'" % SECRETS[3], 80.0, comp="plugin:alpha")])])
cp, rep, d = run(["diagnose", "{d}/b.json", "--json", "--out", "{d}/out.json"], {"b.json": sec})
blob = cp.stdout + cp.stderr + (open(os.path.join(d, "out.json")).read() if os.path.exists(os.path.join(d, "out.json")) else "")
leaked = [s for s in SECRETS if s in blob]
cp2, _, _ = run(["diagnose", "{d}/b.json"], {"b.json": sec})
leaked_text = [s for s in SECRETS if s in cp2.stdout + cp2.stderr]
probe("E01", not leaked and not leaked_text, {"leaked_json": leaked, "leaked_text": leaked_text, "note": "SMTP_PASS is not matched by the doc's secret list; value also placed in a SQL literal"})

# ---- --out rules
cp, rep, d = run(["diagnose", "{d}/b.json", "--json", "--out", "{d}/out.json"], {"b.json": B(wp_config={"WP_CACHE": True})})
outj = json.load(open(os.path.join(d, "out.json"))) if os.path.exists(os.path.join(d, "out.json")) else None
probe("O01a", outj is not None and [f["code"] for f in outj.get("findings", [])] == ["CONFIG_CACHE_DROPIN_MISSING"], {"rc": cp.returncode, "out_codes": codes(outj)})
probe("O01b", rep is not None and rep.get("findings") == (outj or {}).get("findings"), {"stdout_is_json": rep is not None, "stdout_head": cp.stdout[:80], "note": "doc synopsis allows --json with --out; is stdout still JSON"})
before = json.dumps(B())
cp, rep, d = run(["diagnose", "{d}/b.json", "--out", "{d}/b.json"], {"b.json": B()})
probe("O02", cp.returncode == 2 and open(os.path.join(d, "b.json")).read() == before and not tb(cp), {"rc": cp.returncode})
cp, rep, d = run(["diagnose", "{d}/sub/../b.json", "--out", "{d}/b.json"], {"b.json": B(), "sub/x": "x"})
probe("O03", cp.returncode == 2 and open(os.path.join(d, "b.json")).read() == before, {"rc": cp.returncode, "note": "same input via another path spelling"})
cp, rep, d = run(["diagnose", "{d}/bad.json", "--out", "{d}/out.json"], {"bad.json": "{", "out.json": "PREVIOUS"})
probe("O04", cp.returncode == 2 and open(os.path.join(d, "out.json")).read() == "PREVIOUS", {"rc": cp.returncode})
cp, rep, d = run(["diagnose", "{d}/b.json", "--out", "{d}/nodir/out.json"], {"b.json": B()})
probe("O05", cp.returncode == 2 and not tb(cp), {"rc": cp.returncode, "traceback": tb(cp), "stderr": cp.stderr[-160:]})
d = tempfile.mkdtemp(prefix="m23r1-", dir="/tmp"); open(os.path.join(d, "b.json"), "w").write(before); os.symlink(os.path.join(d, "b.json"), os.path.join(d, "alias.json"))
cp = subprocess.run([PY, TOOL, "diagnose", os.path.join(d, "b.json"), "--out", os.path.join(d, "alias.json")], capture_output=True, text=True, timeout=60)
probe("O06", cp.returncode == 2 and open(os.path.join(d, "b.json")).read() == before, {"rc": cp.returncode, "input_intact": open(os.path.join(d, "b.json")).read() == before, "note": "--out is a symlink to the input"})

# ---- compare rules
def samples(url, vals, start=0):
    return [req("s%d" % (start + i), url, float(v)) for i, v in enumerate(vals)]
BEF = [800, 810, 790, 805, 795]
AFT = [400, 410, 390, 405, 395]
def cmp(pid, b, a, want_rc, want_claim, note=""):
    cp, rep, d = run(["compare", "{d}/b.json", "{d}/a.json", "--json"], {"b.json": b, "a.json": a})
    claim = (rep or {}).get("speedup_claimed")
    ok = cp.returncode == want_rc and claim == want_claim and not tb(cp) if want_rc is not None else claim == want_claim and not tb(cp)
    probe(pid, ok, {"rc": cp.returncode, "claimed": claim, "why": (rep or {}).get("not_comparable_because"), "urls": (rep or {}).get("urls"), "note": note})
cmp("P01", B(requests=samples("/", BEF)), B(requests=samples("/", AFT)), 0, True)
cmp("P02", B(requests=samples("/", BEF)), B(measurement={"warm_cache": True}, requests=samples("/", AFT)), 3, False)
cmp("P03", B(requests=samples("/", BEF)), B(env={"php": "8.2.0"}, requests=samples("/", AFT)), 3, False)
cmp("P04", B(requests=samples("/", BEF)), B(measurement={"concurrency": 4}, requests=samples("/", AFT)), 3, False)
cmp("P05", B(requests=samples("/", BEF)), B(requests=samples("/shop/", AFT)), 3, False)
cmp("P06", B(requests=samples("/", BEF[:4])), B(requests=samples("/", AFT[:4])), 3, False)
cmp("P07", B(requests=samples("/", BEF)), B(requests=samples("/", AFT + [400])), 3, False)
cmp("P08", B(requests=samples("/", BEF)), B(requests=samples("/", [400, 410, 390, 405, 800])), None, False, "overlap: inconclusive, no claim")
cmp("P09", B(requests=samples("/", BEF) + samples("/a", BEF, 10)), B(requests=samples("/", AFT) + samples("/a", BEF, 10)), None, False, "one URL unchanged: no overall claim")
cmp("P10", B(requests=samples("/", BEF)), B(site="other", requests=samples("/", AFT)), 3, False)
cmp("P11", B(requests=samples("/", BEF)), B(environment="staging", requests=samples("/", AFT)), 3, False)
cmp("P12", B(requests=samples("/", BEF)), B(requests=samples("/", [790, 400, 400, 400, 400])), None, False, "max(after)=790 equals min(before)=790: not every after beats every before")
cmp("P13", B(requests=samples("/", BEF)), B(measurement={"tool": "other"}, requests=samples("/", AFT)), 3, False)
cmp("P14", B(requests=samples("/", BEF)), B(measurement={"runs_per_url": 7}, requests=samples("/", AFT)), 3, False, "declared runs_per_url differs; samples equal")
cmp("P15", B(requests=samples("/", BEF)), B(source="different capture", requests=samples("/", AFT)), 0, True, "source text is not in the comparability list; finding-only if refused")
cmp("P16", B(requests=samples("/", BEF)), B(measurement={"warm_cache": None}, requests=samples("/", AFT)), None, False, "after warm_cache unknown (null) vs false: is unknown treated as the same measurement")
json.dump(results, open(os.path.join(OUT, "probes.json"), "w"), indent=1)
print("TOTAL %d/%d" % (sum(r["result"] == "PASS" for r in results), len(results)))
