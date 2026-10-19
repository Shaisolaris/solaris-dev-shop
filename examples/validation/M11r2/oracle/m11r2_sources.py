# M11 r2 per-source oracle (Grok self-validation, not independent review). Black box: expectations come from
# incident-slo.md ("Sources", "Duplicates", "Conflicting minutes", "Missing telemetry", "Values"), computed here with
# Fractions. Core rows score; OBS rows record only. Usage: PY m11r2_sources.py REPO OUT.json [--tool PATH]
import json, random, shutil, subprocess, sys, tempfile
from fractions import Fraction as F
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
TOOL = Path(sys.argv[sys.argv.index("--tool") + 1]) if "--tool" in sys.argv else REPO / "employees/infrastructure/site-reliability-engineer/incident_slo.py"
D = Path(tempfile.mkdtemp(prefix="m11r2o-", dir="/tmp")); ROWS = []
def m(i): return "2026-09-07T%02d:%02d:00Z" % (13 + i // 60, i % 60)
def six(x): return str(Decimal(x.numerator) / Decimal(x.denominator) if False else (Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))
def run(tel, minutes=60, obj="0.99", name="b"):
    b = {"schema": "solaris.incident-bundle/1", "service": "ledger-sync", "window": {"start": m(0), "end": m(minutes)},
         "slo": {"objective": float(obj)}, "telemetry": tel, "events": []}
    p = D / (name + ".json"); p.write_text(json.dumps(b))
    cp = subprocess.run([sys.executable, str(TOOL), "report", str(p), "--json"], capture_output=True, text=True,
                        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(D)}, timeout=60)
    try: r = json.loads(cp.stdout) if cp.returncode == 0 else {}
    except Exception: r = {}
    return cp.returncode, r
def expect(tel, minutes=60, obj="0.99", minc=F(9, 10)):
    """Doc rule: per minute, per source the set of distinct (good,total); >1 distinct for any source -> conflicting;
    else sum over sources. Missing = no record. Values exact."""
    per = {}
    for t in tel:
        per.setdefault(t["minute"], {}).setdefault(t.get("source", None), set()).add((t["good"], t["total"]))
    conf = sorted(k for k, s in per.items() if any(len(v) > 1 for v in s.values()))
    good = total = meas = 0
    for k, s in per.items():
        if k in conf: continue
        meas += 1; good += sum(next(iter(v))[0] for v in s.values()); total += sum(next(iter(v))[1] for v in s.values())
    o = F(obj); bad = total - good; cov = F(meas, minutes)
    st = "insufficient_telemetry" if cov < minc else ("met" if total and F(good, total) >= o else "breached")
    e = {"good": good, "total": total, "bad": bad, "measured_minutes": meas, "coverage": six(cov), "status": st,
         "conflicting_minutes": len(conf), "missing_minutes": minutes - len(per)}
    if total:
        e["availability"] = six(F(good, total)); e["burn_rate"] = six(F(bad, total) / (1 - o))
    return e
def got(r):
    s = r.get("slo", {}); mt = r.get("missing_telemetry", {})
    g = {k: s.get(k) for k in ("good", "total", "bad", "measured_minutes", "coverage", "status", "availability", "burn_rate")}
    g["conflicting_minutes"] = mt.get("conflicting_minutes"); g["missing_minutes"] = mt.get("minutes"); return g
def cmp(e, g): return {k: (e[k], g.get(k)) for k in e if e[k] != g.get(k)}
def row(rid, kind, ok, det): ROWS.append({"id": rid, "kind": kind, "result": ("PASS" if ok else "FAIL") if kind == "core" else "OBS", "detail": det})
def case(rid, tel, minutes=60, extra=None, **kw):
    rc, r = run(tel, minutes, name=rid); e = expect(tel, minutes); g = got(r); bad = cmp(e, g)
    ok = rc == 0 and not bad and (extra(r) if extra else True)
    row(rid, "core", ok, {"rc": rc, "mismatch": bad, "status": g.get("status"), "total": g.get("total"), "labels": r.get("labels")}); return r
# S01: three load balancers, errors only on lb-2 in minutes 20-22: whole traffic measured; 3 impact minutes
# (v2: v1 also asserted "breached", my own arithmetic error: 120 bad of 54000 is met at 0.99; kept as _v1)
tel = [dict(minute=m(i), good=(300 - 40 if s == "lb-2" and 20 <= i <= 22 else 300), total=300, source=s) for i in range(60) for s in ("lb-0", "lb-1", "lb-2")]
case("S01_three_sources_summed", tel, extra=lambda r: r["impact"]["minutes"] == 3)
# S02: four sources, identical counts every minute: all four count
case("S02_equal_counts_four_sources", [dict(minute=m(i), good=250, total=250, source="lb-%d" % s) for i in range(60) for s in range(4)])
# S03: a source re-delivers its own minute (same counts, later received_at): counted once
tel = [dict(minute=m(i), good=499, total=500, source=s) for i in range(60) for s in ("a", "b")] + [dict(minute=m(i), good=499, total=500, source="a", received_at=m(i + 1)) for i in range(0, 60, 3)]
case("S03_same_source_repeat_once", tel)
# S04: one source two counts for a minute: the whole minute (both sources) is out; other source's error dropped too (doc)
tel = [dict(minute=m(i), good=500, total=500, source=s) for i in range(60) for s in ("a", "b")] + [dict(minute=m(7), good=480, total=500, source="a"), dict(minute=m(7), good=100, total=500, source="b")]
tel = [t for t in tel if not (t["minute"] == m(7) and t["source"] == "b" and t["good"] == 500)]
case("S04_one_source_conflict_drops_minute", tel, extra=lambda r: any("conflicting" in l for l in r.get("labels", [])))
# S05: unnamed records are one source: unnamed + named summed; two unnamed different counts conflict
tel = [dict(minute=m(i), good=400, total=400) for i in range(60)] + [dict(minute=m(i), good=100, total=100, source="lb-x") for i in range(60)] + [dict(minute=m(9), good=300, total=400)]
case("S05_unnamed_is_one_source", tel)
# S06: r1-style bundle without sources (equal repeats and a conflict) behaves as one source
tel = [dict(minute=m(i), good=995, total=1000) for i in range(60)] + [dict(minute=m(5), good=995, total=1000)] + [dict(minute=m(6), good=900, total=1000)]
case("S06_no_source_bundle_r1_semantics", tel)
# S07: property test, 40 random bundles: 1-4 sources, random gaps, repeats, conflicts, errors, unnamed source mixed in
rng = random.Random(1119); fails = []
for k in range(40):
    srcs = ["s%d" % j for j in range(rng.randint(1, 4))] + ([None] if rng.random() < 0.3 else []); tel = []; mins = rng.choice([30, 60, 120])
    for i in range(mins):
        for s in srcs:
            if rng.random() < 0.05: continue
            tot = rng.randint(1, 400); g = tot - (rng.randint(0, tot // 5) if rng.random() < 0.15 else 0); rec = dict(minute=m(i), good=g, total=tot)
            if s is not None: rec["source"] = s
            tel.append(rec)
            if rng.random() < 0.05: tel.append(dict(rec))
            if rng.random() < 0.02: c = dict(rec); c["good"] = max(0, g - 1) if g else 1; c["total"] = max(tot, c["good"]); tel.append(c)
    rng.shuffle(tel); rc, r = run(tel, mins, name="S07_%d" % k); e = expect(tel, mins); bad = cmp(e, got(r))
    if rc != 0 or bad: fails.append({"case": k, "rc": rc, "mismatch": bad})
row("S07_random_sources_property", "core", not fails, {"cases": 40, "fails": fails[:3]})
# S08: per-source error minute drives impact, burn and decision path the same as one combined source (equivalence)
split = [dict(minute=m(i), good=(450 if i == 30 and s == "a" else 500), total=500, source=s) for i in range(60) for s in ("a", "b")]
one = [dict(minute=m(i), good=(950 if i == 30 else 1000), total=1000) for i in range(60)]
rc1, r1 = run(split, name="S08a"); rc2, r2 = run(one, name="S08b")
strip = lambda r: {k: r.get(k) for k in ("slo", "impact", "missing_telemetry", "decision")}
row("S08_split_equals_combined", "core", rc1 == rc2 == 0 and strip(r1) == strip(r2), {"same": strip(r1) == strip(r2), "status": r1.get("slo", {}).get("status")})
# OBS rows (doc silent)
part = [dict(minute=m(i), good=500, total=500, source=s) for i in range(60) for s in ("a", "b") if not (s == "b" and 10 <= i < 40)]
rc, r = run(part, name="O09"); row("O09_partial_source_dropout", "OBS", True, {"rc": rc, "measured_minutes": r.get("slo", {}).get("measured_minutes"), "total": r.get("slo", {}).get("total"), "labels": r.get("labels"), "note": "one of two LBs silent for 30 min: minutes still count as measured"})
rc, r = run([dict(minute=m(i), good=500, total=500, source=s) for i in range(60) for s in ("lb-0", "LB-0 ")], name="O10")
row("O10_source_name_case_space", "OBS", True, {"rc": rc, "total": r.get("slo", {}).get("total")})
rc, r = run([dict(minute=m(i), good=500, total=500, source=s) for i in range(60) for s in ("", None)] and [dict(minute=m(i), good=500, total=500, source="") for i in range(60)] + [dict(minute=m(i), good=500, total=500) for i in range(60)], name="O11")
row("O11_empty_string_vs_missing_source", "OBS", True, {"rc": rc, "total": r.get("slo", {}).get("total"), "conflicting": r.get("missing_telemetry", {}).get("conflicting_minutes")})
rc, r = run([dict(minute=m(i), good=500, total=500, source=7) for i in range(60)], name="O12")
row("O12_non_string_source", "OBS", True, {"rc": rc})
rc, r = run([dict(minute=m(i), good=500, total=500, source=s) for i in range(60) for s in ("a", "b")] + [dict(minute=m(3), good=500, total=500, source="mirror-of-a")], name="O13")
row("O13_mirror_added_as_documented", "OBS", True, {"rc": rc, "total": r.get("slo", {}).get("total")})
shutil.rmtree(D)
json.dump(ROWS, open(OUT, "w"), indent=1, sort_keys=True)
for x in ROWS: print(x["id"], x["result"], json.dumps(x["detail"], sort_keys=True)[:300])
c = [x for x in ROWS if x["kind"] == "core"]; print("M11R2 SOURCES %d/%d core PASS" % (sum(x["result"] == "PASS" for x in c), len(c)))
