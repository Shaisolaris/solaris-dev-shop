#!/usr/bin/env python3
"""M11 r3 expected-sources oracle (Grok self-validation, not independent review; black box). Expectations come from
the r3 incident-slo.md text ("Sources", "Expected sources", "Source names", "Missing telemetry", decision rule 3),
computed here with Fractions; the r3 change is builder design. Aimed at sources retired or added inside the window,
name normalization, and recovery by declaring sources or splitting the window. Core rows score; OBS rows record
only. Authoring fix before scoring (disclosed): T14 first compared the tool's display name "(unnamed)" for the
unnamed source with my None; the doc names no label, so "(unnamed)" is dropped from that comparison. Usage: PY m11r3_sources.py REPO OUT.json [--tool PATH]"""
import json, random, shutil, subprocess, sys, tempfile
from fractions import Fraction as F
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
TOOL = Path(sys.argv[sys.argv.index("--tool") + 1]) if "--tool" in sys.argv else REPO / "employees/infrastructure/site-reliability-engineer/incident_slo.py"
D = Path(tempfile.mkdtemp(prefix="m11r3o-", dir="/tmp")); ROWS = []; K = [0]
def m(i): return "2026-09-07T%02d:%02d:00Z" % (12 + i // 60, i % 60)
def six(x): return str((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))
def norm(s): return None if s is None else " ".join(s.split()).casefold()
def bundle(tel, w0=0, w1=200, obj="0.99", declared=None, change_at=None):
    b = {"schema": "solaris.incident-bundle/1", "service": "ledger-sync", "window": {"start": m(w0), "end": m(w1)}, "slo": {"objective": float(obj)}, "telemetry": tel, "events": []}
    if declared is not None: b["telemetry_sources"] = declared
    if change_at is not None: b["change"] = {"revision": "v8.0.1", "previous": "v8.0.0", "deployed_at": m(change_at)[:-3] + "40Z", "migrates_data": False}
    return b
def run(b):
    K[0] += 1; p = D / ("b%03d.json" % K[0]); p.write_text(json.dumps(b)); h = p.read_bytes()
    cp = subprocess.run([sys.executable, str(TOOL), "report", str(p), "--json"], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(D)}, timeout=60)
    try: r = json.loads(cp.stdout) if cp.returncode == 0 else {}
    except Exception: r = {}
    return cp.returncode, r, cp
def ranges(ms, w0):
    out = []; ms = sorted(ms)
    for x in ms:
        if out and out[-1][1] == x: out[-1][1] = x + 1
        else: out.append([x, x + 1])
    return [{"start": m(a), "end": m(b), "minutes": b - a} for a, b in out]
def expect(b, minc=F(9, 10)):
    """Doc rule. Returns None when the bundle must be refused (exit 2)."""
    tel = b["telemetry"]; w0 = int(b["window"]["start"][11:13]) * 60 + int(b["window"]["start"][14:16]) - 720; w1 = int(b["window"]["end"][11:13]) * 60 + int(b["window"]["end"][14:16]) - 720
    spell = {}
    for t in tel:
        s = t.get("source"); spell.setdefault(norm(s), set()).add(s)
    if any(len(v) > 1 for k, v in spell.items() if k is not None): return None
    dec = b.get("telemetry_sources")
    if dec is not None:
        nd = [norm(x) for x in dec]
        if len(set(nd)) != len(nd): return None
        if any(norm(t.get("source")) not in nd for t in tel): return None
        exp = set(nd); basis = "declared"
    else:
        exp = {norm(t.get("source")) for t in tel if w0 <= mi(t) < w1}; basis = "inferred"
    per = {}
    for t in tel:
        i = mi(t)
        if not (w0 <= i < w1): continue
        per.setdefault(i, {}).setdefault(norm(t.get("source")), set()).add((t["good"], t["total"]))
    conf = {i for i, s in per.items() if any(len(v) > 1 for v in s.values())}
    part = {i for i, s in per.items() if i not in conf and not exp <= set(s)}
    good = total = meas = 0
    for i, s in per.items():
        if i in conf or i in part: continue
        meas += 1; good += sum(next(iter(v))[0] for v in s.values()); total += sum(next(iter(v))[1] for v in s.values())
    n = w1 - w0; o = F(b["slo"]["objective"]).limit_denominator(10 ** 6); cov = F(meas, n)
    breach = bool(total) and F(good, total) < o
    if cov < minc: st = "insufficient_telemetry"
    elif breach: st = "breached"
    elif part: st = "insufficient_telemetry"
    else: st = "met"
    silent = {s: sorted(i for i in part if s not in per[i]) for s in exp}
    return {"good": good, "total": total, "measured_minutes": meas, "coverage": six(cov), "status": st, "partial_minutes": len(part), "partial_ranges": ranges(part, w0),
            "missing_minutes": n - len(per), "basis": basis, "expected": sorted(x for x in exp if x is not None), "silent": silent, "part": part, "per": per}
def mi(t): return int(t["minute"][11:13]) * 60 + int(t["minute"][14:16]) - 720
def got(r):
    s = r.get("slo", {}); mt = r.get("missing_telemetry", {}); so = r.get("sources", {})
    return {"good": s.get("good"), "total": s.get("total"), "measured_minutes": s.get("measured_minutes"), "coverage": s.get("coverage"), "status": s.get("status"), "partial_minutes": mt.get("partial_minutes"),
            "partial_ranges": mt.get("partial_ranges"), "missing_minutes": mt.get("minutes"), "basis": so.get("basis"), "expected": sorted(norm(x) for x in (so.get("expected") or []) if x is not None and x != "(unnamed)")}
def row(rid, ok, det, obs=False): ROWS.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": det})
def case(rid, b, extra=None):
    rc, r, cp = run(b); e = expect(b)
    if e is None:
        row(rid, rc == 2 and not r and "Traceback" not in cp.stderr, {"rc": rc, "want": "exit 2", "stderr": cp.stderr.strip()[-200:]}); return r
    g = got(r); bad = {k: (e[k], g.get(k)) for k in g if e[k] != g.get(k)}
    ex = extra(r, e) if extra else True
    row(rid, rc == 0 and not bad and ex, {"rc": rc, "mismatch": bad, "status": g.get("status"), "partial": g.get("partial_minutes"), "extra_ok": ex}); return r
def tel_of(srcs, n=200, good=lambda i, s: 300, total=lambda i, s: 300, alive=lambda i, s: True):
    return [dict(minute=m(i), good=good(i, s), total=total(i, s), source=s) for i in range(n) for s in srcs if alive(i, s)]
def per_source_ok(r, e):
    ps = {norm(x["source"]): x for x in (r.get("sources") or {}).get("per_source", [])}
    for s in e["expected"]:
        x = ps.get(s)
        if x is None: return False
        if x.get("silent_while_others_report") != len(e["silent"][s]): return False
    return True
# T01 clean control: three load balancers all window, inferred basis: met, no partial minutes
case("T01_clean_three_sources_met", bundle(tel_of(["lb-0", "lb-1", "lb-2"])), lambda r, e: r["slo"]["status"] == "met")
# T02 a source retired at minute 190 of 200 (inferred): 10 partial minutes, coverage 0.95 stays above 0.9, so the
# status is insufficient_telemetry only because of the partial rule; the retired source's silent range is named
r = case("T02_source_retired_mid_window", bundle(tel_of(["lb-0", "lb-1", "lb-2"], alive=lambda i, s: not (s == "lb-2" and i >= 190))), per_source_ok)
# T03 a source added at minute 10: minutes 0-9 partial
case("T03_source_added_mid_window", bundle(tel_of(["lb-0", "lb-1", "lb-3"], alive=lambda i, s: not (s == "lb-3" and i < 10))), per_source_ok)
# T04 a source retired and replaced (lb-2 until 100, lb-9 from 100): both look silent half the window -> 200 partial minutes
case("T04_source_replaced_mid_window", bundle(tel_of(["lb-0", "lb-2", "lb-9"], alive=lambda i, s: not ((s == "lb-2" and i >= 100) or (s == "lb-9" and i < 100)))), per_source_ok)
# T05 recovery: split the window at the retirement and declare each part's sources: both parts met, no partial
t = tel_of(["lb-0", "lb-1", "lb-2"], alive=lambda i, s: not (s == "lb-2" and i >= 190))
case("T05a_recovery_split_before", bundle([x for x in t if mi(x) < 190], 0, 190, declared=["lb-0", "lb-1", "lb-2"]), lambda r, e: r["slo"]["status"] == "met")
case("T05b_recovery_split_after", bundle([x for x in t if mi(x) >= 190], 190, 200, declared=["lb-0", "lb-1"]), lambda r, e: r["slo"]["status"] == "met")
# T06 declared list without the retired source while its records remain: refused (record names another source)
case("T06_declared_list_missing_a_reporting_source_refused", bundle(t, declared=["lb-0", "lb-1"]))
# T07 a breach in complete minutes is still reported while partial minutes exist
case("T07_breach_in_complete_minutes_still_reported", bundle(tel_of(["lb-0", "lb-1", "lb-2"], good=lambda i, s: 200 if 20 <= i < 40 else 300, alive=lambda i, s: not (s == "lb-2" and i >= 190))), lambda r, e: r["slo"]["status"] == "breached")
# T08 errors only while a source is silent: partial minutes are not impact minutes (doc), status not met
case("T08_errors_only_in_partial_minutes", bundle(tel_of(["lb-0", "lb-1", "lb-2"], good=lambda i, s: 0 if i >= 190 else 300, alive=lambda i, s: not (s == "lb-2" and i >= 190))),
     lambda r, e: (r.get("impact") or {}).get("minutes", 0) == 0 and r["slo"]["status"] != "met")
# T09 normalization: records " LB-A" and "us  east" with declared ["lb-a", "US EAST"]: accepted, measured whole
case("T09_names_trimmed_collapsed_casefolded", bundle(tel_of([" LB-A", "us  east"]), declared=["lb-a", "US EAST"]), lambda r, e: r["slo"]["total"] == 200 * 600)
# T10 two spellings of one name inside the telemetry: refused
case("T10_two_spellings_refused", bundle(tel_of(["lb-0", "lb-1"]) + [dict(minute=m(5), good=300, total=300, source="LB-0 ")]))
# T11 declared list naming one source twice (after normalization): refused
case("T11_declared_duplicate_refused", bundle(tel_of(["lb-a", "lb-b"]), declared=["lb-a", "LB-A", "lb-b"]))
# T12 declared list plus a record with no source: refused
case("T12_unnamed_record_with_declared_list_refused", bundle(tel_of(["lb-a", "lb-b"]) + [dict(minute=m(3), good=10, total=10)], declared=["lb-a", "lb-b"]))
# T13 a declared source that never reports: every minute partial
case("T13_declared_never_reporting", bundle(tel_of(["lb-a", "lb-b"]), declared=["lb-a", "lb-b", "lb-c"]))
# T14 one unnamed source (regression): no partial minutes, met
case("T14_single_unnamed_source", bundle([dict(minute=m(i), good=1000, total=1000) for i in range(200)]), lambda r, e: r["slo"]["status"] == "met")
# T15 decision rule 3: change at minute 100, no budget-burning minute, a source silent after the change -> insufficient_evidence;
#     the same with every source reporting -> do_not_rollback
def dec(r): return ((r or {}).get("decision") or {}).get("decision")
r1 = case("T15a_silent_after_change_insufficient_evidence", bundle(tel_of(["lb-0", "lb-1", "lb-2"], alive=lambda i, s: not (s == "lb-2" and i >= 190)), change_at=100), lambda r, e: dec(r) == "insufficient_evidence")
r2 = case("T15b_all_report_after_change_do_not_rollback", bundle(tel_of(["lb-0", "lb-1", "lb-2"]), change_at=100), lambda r, e: dec(r) == "do_not_rollback")
# T16 property: 40 bundles, 2-4 sources with random add/retire/outage, random normalization-safe spellings, optional declared list
rnd = random.Random(1103); bad = []
for k in range(40):
    ns = rnd.randint(2, 4); srcs = ["lb-%d" % j for j in range(ns)]; life = {}
    for s in srcs:
        a = rnd.choice([0, 0, rnd.randint(1, 30)]); z = rnd.choice([200, 200, rnd.randint(170, 199)]); out = (rnd.randint(0, 199), rnd.randint(0, 6)) if rnd.random() < 0.3 else (0, 0); life[s] = (a, z, out)
    alive = lambda i, s: life[s][0] <= i < life[s][1] and not (life[s][2][0] <= i < life[s][2][0] + life[s][2][1])
    tel = tel_of(srcs, good=lambda i, s: 300 - (rnd.randint(0, 9) if rnd.random() < 0.1 else 0), alive=alive)
    rnd.shuffle(tel); decl = (srcs if rnd.random() < 0.4 else None)
    b = bundle(tel, declared=decl); rc, r, cp = run(b); e = expect(b); g = got(r) if e is not None else None
    ok = (rc == 2) if e is None else (rc == 0 and all(e[x] == g.get(x) for x in g))
    if not ok: bad.append({"k": k, "rc": rc, "life": life, "declared": decl, "mismatch": None if e is None else {x: (e[x], g.get(x)) for x in g if e[x] != g.get(x)}})
row("T16_random_lifetimes_property", not bad, {"run": 40, "mismatches": bad[:3]})
# OBS: what a reader sees for T02 (labels, per-source entry, timeline source_silent count), and import counts
rc, r, _ = run(bundle(tel_of(["lb-0", "lb-1", "lb-2"], alive=lambda i, s: not (s == "lb-2" and i >= 190))))
row("O17_retired_source_reader_view", True, {"labels": r.get("labels"), "lb2": [x for x in (r.get("sources") or {}).get("per_source", []) if x.get("source") == "lb-2"],
    "timeline_source_silent": sum(1 for x in r.get("timeline", []) if "silent" in json.dumps(x)), "import": r.get("import")}, obs=True)
shutil.rmtree(D, ignore_errors=True)
json.dump(ROWS, open(OUT, "w"), indent=1, default=str)
for x in ROWS: print(x["id"], x["result"], json.dumps(x["detail"], default=str)[:400])
c = [x for x in ROWS if x["kind"] == "core"]; print("M11R3 SOURCES %d/%d core PASS" % (sum(x["result"] == "PASS" for x in c), len(c)))
