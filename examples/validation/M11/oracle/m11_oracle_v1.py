#!/usr/bin/env python3
"""M11 oracle (Grok self-validation, written by Grok, black box). Expectations come from incident-slo.md and the
G11 README, never from the tool's output. Bundles are generated here (service, window and counts differ from the
builder's fixtures); expected values use Fraction and Decimal half-even rounding.
Usage: PY m11_oracle.py REPO [--tool TOOL.py] OUT.json. Core rows (E*) score; OBS rows record only."""
import json, os, random, shutil, subprocess, sys, tempfile, hashlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); a = sys.argv[2:]
TOOL = REPO / "employees/infrastructure/site-reliability-engineer/incident_slo.py"
if a and a[0] == "--tool": TOOL = Path(a[1]).resolve(); a = a[2:]
OUT = a[0]; PY = sys.executable; ENV = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
TOP = Path(tempfile.mkdtemp(prefix="m11top-", dir="/tmp")).resolve(); rows = []
def row(rid, ok, detail, obs=False):
    rows.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": detail})
def guard(rid, f):
    try: f()
    except Exception as e: row(rid, False, "harness or tool crash: %r" % (e,))
def d6(fr): return str(Decimal(fr.numerator) / Decimal(fr.denominator) if False else (Decimal(fr.numerator) / Decimal(fr.denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN)) if fr.denominator != 1 or True else None
from decimal import getcontext; getcontext().prec = 60
def iso(t): return t.strftime("%Y-%m-%dT%H:%M:%SZ")
T0 = datetime(2026, 9, 7, 13, 0, tzinfo=timezone.utc)
def bundle(n=90, svc="ledger-sync", obj="0.995", burn=6, cov=0.9, seed=1, bad=None, change_min=30, change=True, events=None, drop=(), extra_tel=(), traffic=None):
    r = random.Random(seed); tel = []; per = {}
    for i in range(n):
        if i in drop: continue
        tot = traffic(i) if traffic else r.randint(800, 1300)
        b = bad(i, tot) if bad else (1 if r.random() < 0.3 else 0)
        per[i] = (tot - b, tot); tel.append({"minute": iso(T0 + timedelta(minutes=i)), "good": tot - b, "total": tot, "source": "lb-%d" % (i % 3)})
    tel += list(extra_tel)
    b = {"schema": "solaris.incident-bundle/1", "service": svc, "window": {"start": iso(T0), "end": iso(T0 + timedelta(minutes=n))},
         "slo": {"objective": float(obj), "rollback_burn_rate": burn, "min_coverage": cov}, "telemetry": tel, "events": events if events is not None else []}
    if change: b["change"] = {"revision": "v7.3.1", "previous": "v7.3.0", "deployed_at": iso(T0 + timedelta(minutes=change_min, seconds=40)), "migrates_data": False}
    return b, per
def expect(per, obj):
    o = Fraction(obj); g = sum(v[0] for v in per.values()); t = sum(v[1] for v in per.values()); bad = t - g
    return {"good": g, "total": t, "bad": bad, "availability": d6(Fraction(g, t)), "error_budget_requests": d6((1 - o) * t), "burn_rate": d6(Fraction(bad, t) / (1 - o)),
            "budget_consumed": d6(Fraction(bad) / ((1 - o) * t)), "budget_remaining": d6(1 - Fraction(bad) / ((1 - o) * t))}
def run(b, name, *extra):
    d = TOP / name; d.mkdir(parents=True, exist_ok=True); p = d / "bundle.json"; p.write_text(json.dumps(b))
    cp = subprocess.run([PY, str(TOOL), "report", str(p), "--json"] + list(extra), cwd=d, env=ENV, capture_output=True, text=True, timeout=300)
    try: rep = json.loads(cp.stdout)
    except Exception: rep = None
    return cp.returncode, rep, cp.stdout
def slo_ok(rep, exp):
    s = (rep or {}).get("slo", {}); diff = {k: (s.get(k), v) for k, v in exp.items() if s.get(k) != v}; return not diff, diff
def impact_minutes(per, obj): o = Fraction(obj); return sorted(i for i, (g, t) in per.items() if t and Fraction(t - g, t) > 1 - o)

def e01():  # clean control: errors well under objective
    b, per = bundle(seed=3); rc, rep, _ = run(b, "e01"); exp = expect(per, "0.995"); ok, diff = slo_ok(rep, exp)
    dec = (rep or {}).get("decision", {})
    ok = rc == 0 and ok and rep["slo"]["status"] == "met" and dec.get("decision") == "do_not_rollback" and not impact_minutes(per, "0.995")
    row("E01_clean_control_exact", ok, {"rc": rc, "diff": diff, "status": (rep or {}).get("slo", {}).get("status"), "decision": dec.get("decision")})
def e02():  # regression after the change, exact SLO, impact, response times, decision trace names service/window/revision
    reg = range(33, 51)
    ev = [{"id": "pg-1", "at": iso(T0 + timedelta(minutes=35, seconds=10)), "kind": "detected", "actor": "alerting"},
          {"id": "mt-1", "at": iso(T0 + timedelta(minutes=50, seconds=5)), "kind": "mitigated"}, {"id": "rs-1", "at": iso(T0 + timedelta(minutes=58)), "kind": "resolved"}]
    b, per = bundle(seed=4, bad=lambda i, t: (t // 6 if i in reg else 0), events=ev); rc, rep, _ = run(b, "e02"); exp = expect(per, "0.995"); ok, diff = slo_ok(rep, exp)
    im = impact_minutes(per, "0.995"); st = T0 + timedelta(minutes=im[0]); en = T0 + timedelta(minutes=im[-1] + 1)
    imp = (rep or {}).get("impact", {}); resp = (rep or {}).get("response", {}); dec = (rep or {}).get("decision", {})
    want_resp = {"time_to_detect_s": 35 * 60 + 10 - im[0] * 60, "time_to_mitigate_s": 50 * 60 + 5 - im[0] * 60, "time_to_resolve_s": 58 * 60 - im[0] * 60}
    win = "%s/%s" % (b["window"]["start"], b["window"]["end"])
    names = all(x in json.dumps(dec) for x in ("ledger-sync", "v7.3.1", win))
    ok = rc == 0 and ok and rep["slo"]["status"] == "breached" and imp.get("start") == iso(st) and imp.get("end") == iso(en) and imp.get("minutes") == len(im) and \
        {k: resp.get(k) for k in want_resp} == want_resp and dec.get("decision") == "rollback" and names
    row("E02_regression_exact_and_trace_names", ok, {"rc": rc, "diff": diff, "impact": imp, "want_impact": (iso(st), iso(en), len(im)), "response": resp, "want_response": want_resp, "decision": dec.get("decision"), "trace_names_service_window_revision": names})
def e03():  # denominator: request-weighted availability, traffic spike minutes
    # a few huge-traffic minutes carry all errors: minute-averaged and request-weighted availability differ widely
    b, per = bundle(seed=5, traffic=lambda i: 50000 if i in (40, 41) else 100, bad=lambda i, t: (t // 10 if i in (40, 41) else 0), change_min=80)
    rc, rep, _ = run(b, "e03"); exp = expect(per, "0.995"); ok, diff = slo_ok(rep, exp)
    row("E03_request_weighted_denominator", rc == 0 and ok, {"rc": rc, "diff": diff})
def e04():  # denominator: records outside the window, window narrowed, objective changed
    out = [{"minute": iso(T0 - timedelta(minutes=k)), "good": 0, "total": 5000} for k in (1, 2)] + [{"minute": iso(T0 + timedelta(minutes=90 + k)), "good": 0, "total": 5000} for k in (0, 3)]
    b, per = bundle(seed=6, extra_tel=out, change_min=80); rc, rep, _ = run(b, "e04a"); ok1, d1 = slo_ok(rep, expect(per, "0.995"))
    o1 = (rep or {}).get("import", {}).get("telemetry_outside_window")
    b2 = json.loads(json.dumps(b)); b2["window"] = {"start": iso(T0 + timedelta(minutes=10)), "end": iso(T0 + timedelta(minutes=70))}; b2.pop("change")
    rc2, rep2, _ = run(b2, "e04b"); per2 = {i: v for i, v in per.items() if 10 <= i < 70}; ok2, d2 = slo_ok(rep2, expect(per2, "0.995"))
    b3 = json.loads(json.dumps(b)); b3["slo"]["objective"] = 0.9995; rc3, rep3, _ = run(b3, "e04c"); ok3, d3 = slo_ok(rep3, expect(per, "0.9995"))
    ok = rc == 0 and ok1 and o1 == 4 and rc2 == 0 and ok2 and (rep2 or {}).get("slo", {}).get("minutes") == 60 and rc3 == 0 and ok3
    row("E04_denominator_window_and_objective_changes", ok, {"outside_window_count": o1, "diff_full": d1, "diff_narrow": d2, "diff_obj": d3, "rcs": [rc, rc2, rc3]})
def e05():  # duplicate alerts: same id same content repeated (different received_at) kept once; distinct ids both kept; earliest drives detect
    ev = [{"id": "pg-9", "at": iso(T0 + timedelta(minutes=36)), "kind": "detected", "received_at": iso(T0 + timedelta(minutes=36, seconds=s))} for s in (50, 5, 400)]
    ev += [{"id": "pg-9b", "at": iso(T0 + timedelta(minutes=34, seconds=30)), "kind": "detected"}]
    b, per = bundle(seed=7, bad=lambda i, t: (t // 5 if 33 <= i < 45 else 0), events=ev)
    rc, rep, _ = run(b, "e05"); imp = impact_minutes(per, "0.995")
    det = [x for x in (rep or {}).get("timeline", []) if x.get("id") in ("pg-9", "pg-9b")]
    ok = rc == 0 and len([x for x in det if x["id"] == "pg-9"]) == 1 and len([x for x in det if x["id"] == "pg-9b"]) == 1 and \
        rep["response"].get("time_to_detect_s") == 34 * 60 + 30 - imp[0] * 60 and rep["import"].get("event_duplicates") == 2
    row("E05_duplicate_alerts", ok, {"rc": rc, "timeline_alerts": det, "detect": (rep or {}).get("response", {}).get("time_to_detect_s"), "want_detect": 34 * 60 + 30 - imp[0] * 60, "import": (rep or {}).get("import")})
    pg = [x for x in det if x["id"] == "pg-9"]
    row("E05b_duplicate_kept_record", True, {"kept": pg}, obs=True)
def e06():  # conflicting event content refused; previous --out kept byte-identical
    b, per = bundle(seed=8); d = TOP / "e06"; d.mkdir(); p = d / "b.json"; o = d / "r.json"
    p.write_text(json.dumps(b)); rc1 = subprocess.run([PY, str(TOOL), "report", str(p), "--json", "--out", str(o)], cwd=d, env=ENV, capture_output=True).returncode; before = o.read_bytes() if o.exists() else None
    b["events"] = [{"id": "x1", "at": iso(T0 + timedelta(minutes=5)), "kind": "note", "detail": "a"}, {"id": "x1", "at": iso(T0 + timedelta(minutes=5)), "kind": "note", "detail": "b"}]
    p.write_text(json.dumps(b)); rc2 = subprocess.run([PY, str(TOOL), "report", str(p), "--json", "--out", str(o)], cwd=d, env=ENV, capture_output=True).returncode
    left = sorted(x.name for x in d.iterdir())
    row("E06_conflicting_event_refused_out_kept", rc1 == 0 and rc2 == 2 and before is not None and o.read_bytes() == before and left == ["b.json", "r.json"], {"rcs": [rc1, rc2], "files": left})
def e07():  # repeated import stable: doubled, shuffled, re-delivered under other sources; byte-identical apart from input hash
    b, per = bundle(seed=9, bad=lambda i, t: (t // 7 if 40 <= i < 55 else 0), events=[{"id": "d1", "at": iso(T0 + timedelta(minutes=42)), "kind": "detected"}, {"id": "n1", "at": iso(T0 + timedelta(minutes=42)), "kind": "note"}, {"id": "n0", "at": iso(T0 + timedelta(minutes=42)), "kind": "note"}])
    rc, rep, _ = run(b, "e07a"); outs = []
    for k in range(4):
        r = random.Random(k); c = json.loads(json.dumps(b)); tel = c["telemetry"] + [dict(x, source="replay") for x in c["telemetry"]]; r.shuffle(tel); c["telemetry"] = tel
        ev = c["events"] * 2; r.shuffle(ev); c["events"] = ev; rck, repk, _ = run(c, "e07-%d" % k); 
        for x in (repk or {}), : x.pop("input_sha256", None); x.pop("import", None)
        outs.append((rck, json.dumps(repk, sort_keys=True)))
    base = dict(rep or {}); base.pop("input_sha256", None); base.pop("import", None); bj = json.dumps(base, sort_keys=True)
    rc2, rep2, raw2 = run(b, "e07a"); _, _, raw1 = run(b, "e07a")
    ok = rc == 0 and all(r == 0 and j == bj for r, j in outs) and raw1 == raw2
    row("E07_repeated_import_stable", ok, {"rcs": [r for r, _ in outs], "equal_to_single": [j == bj for _, j in outs], "rerun_identical": raw1 == raw2})
def e08():  # missing telemetry: exact ranges, never counted good, coverage and insufficient_telemetry
    drop = set(range(20, 26)) | {61}
    b, per = bundle(seed=10, drop=drop, change_min=80); rc, rep, _ = run(b, "e08a"); exp = expect(per, "0.995"); ok1, diff = slo_ok(rep, exp)
    mt = (rep or {}).get("missing_telemetry", {}); rng = json.dumps(mt.get("ranges"))
    want = [(iso(T0 + timedelta(minutes=20)), iso(T0 + timedelta(minutes=26))), (iso(T0 + timedelta(minutes=61)), iso(T0 + timedelta(minutes=62)))]
    rng_ok = mt.get("minutes") == 7 and all(s in rng and e in rng for s, e in want)
    cov = (rep or {}).get("slo", {}).get("coverage") == d6(Fraction(83, 90))
    b2, per2 = bundle(seed=10, drop=set(range(0, 20)), change_min=80); rc2, rep2, _ = run(b2, "e08b")
    ok = rc == 0 and ok1 and rng_ok and cov and rep["slo"]["status"] in ("met", "breached") and rc2 == 0 and (rep2 or {}).get("slo", {}).get("status") == "insufficient_telemetry"
    row("E08_missing_telemetry_labelled", ok, {"diff": diff, "missing": mt, "want_ranges": want, "coverage_ok": cov, "low_cov_status": (rep2 or {}).get("slo", {}).get("status")})
    b3, per3 = bundle(seed=11, drop=set(range(31, 45)), bad=lambda i, t: (t // 5 if 31 <= i < 50 else 0)); rc3, rep3, _ = run(b3, "e08c")
    row("E08b_gap_after_change_no_rollback", rc3 == 0 and (rep3 or {}).get("decision", {}).get("decision") == "insufficient_evidence", {"decision": (rep3 or {}).get("decision", {}).get("decision")})
def e09():  # conflicting minutes left out and labelled; partial counts from two collectors are a conflict (documented)
    ex = [{"minute": iso(T0 + timedelta(minutes=12)), "good": 400, "total": 410, "source": "collector-b"}]
    b, per = bundle(seed=12, extra_tel=ex, change_min=80); per.pop(12); rc, rep, _ = run(b, "e09"); ok1, diff = slo_ok(rep, expect(per, "0.995"))
    mt = (rep or {}).get("missing_telemetry", {})
    row("E09_conflicting_minute_left_out", rc == 0 and ok1 and mt.get("conflicting_minutes") == 1, {"diff": diff, "conflicting": mt.get("conflicting_minutes"), "measured": (rep or {}).get("slo", {}).get("measured_minutes")})
def e10():  # late records: >300 s labelled, still used; exactly 300 s is not late
    tel_late = []
    b, per = bundle(seed=13, change_min=80)
    for k, x in enumerate(b["telemetry"][:6]):
        m = datetime.strptime(x["minute"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc); x["received_at"] = iso(m + timedelta(seconds=(301 if k < 3 else 300) + 60))
    rc, rep, _ = run(b, "e10"); ok1, diff = slo_ok(rep, expect(per, "0.995")); lt = (rep or {}).get("import", {}).get("telemetry_late")
    row("E10_late_records_labelled_used", rc == 0 and ok1, {"diff": diff, "telemetry_late": lt}, obs=False)
    row("E10b_late_boundary", True, {"telemetry_late_for_3_at_301s_and_3_at_300s_after_minute_end": lt, "note": "doc does not say whether lateness is measured from the minute start or end"}, obs=True)
def e11():  # ordering: timeline sorted whatever input order; ties deterministic
    ev = [{"id": "e%d" % k, "at": iso(T0 + timedelta(minutes=m, seconds=s)), "kind": kd} for k, (m, s, kd) in enumerate([(50, 0, "resolved"), (5, 0, "note"), (36, 30, "declared"), (35, 0, "detected"), (44, 0, "mitigated"), (36, 30, "status")])]
    b, per = bundle(seed=14, bad=lambda i, t: (t // 6 if 33 <= i < 48 else 0), events=ev); rc, rep, _ = run(b, "e11")
    at = [x.get("at") for x in (rep or {}).get("timeline", [])]
    row("E11_timeline_sorted", rc == 0 and at == sorted(at) and len([x for x in rep["timeline"] if x.get("id", "").startswith("e")]) == 6, {"order": [(x.get("at"), x.get("kind")) for x in (rep or {}).get("timeline", [])][:14]})
def e12():  # decision classes
    res = {}
    b, per = bundle(seed=15, change_min=120); b["change"]["deployed_at"] = iso(T0 + timedelta(minutes=200)); rc, rep, _ = run(b, "e12a"); res["change_outside_window"] = (rep or {}).get("decision", {}).get("decision")
    b, per = bundle(seed=16, bad=lambda i, t: (t // 6 if 10 <= i < 50 else 0)); rc, rep, _ = run(b, "e12b"); res["impact_before_change"] = (rep or {}).get("decision", {}).get("decision")
    b, per = bundle(seed=17, bad=lambda i, t: (t // 150 if 33 <= i < 40 else 0), burn=10); rc, rep, _ = run(b, "e12c"); res["slow_burn_below_threshold"] = (rep or {}).get("decision", {}).get("decision")
    b, per = bundle(seed=18, bad=lambda i, t: (t // 6 if 33 <= i < 50 else 0)); b["change"]["migrates_data"] = True; rc, rep, _ = run(b, "e12d"); res["migrating_no_snapshot"] = (rep or {}).get("decision", {}).get("decision")
    want = {"change_outside_window": "not_applicable", "impact_before_change": "do_not_rollback", "slow_burn_below_threshold": "do_not_rollback", "migrating_no_snapshot": "rollback_blocked"}
    row("E12_decision_classes", res == want, {"got": res, "want": want})
def e13():  # invalid bundles exit 2, nothing written, then a valid one recovers
    res = {}
    def mut(name, f):
        b, per = bundle(seed=19); f(b); rc, rep, out = run(b, "e13-" + name); res[name] = rc
    mut("good_gt_total", lambda b: b["telemetry"][0].update(good=b["telemetry"][0]["total"] + 1))
    mut("negative_total", lambda b: b["telemetry"][0].update(good=-1, total=-1))
    mut("float_counts", lambda b: b["telemetry"][0].update(good=10.5))
    mut("window_not_whole_minute", lambda b: b["window"].update(start=iso(T0 + timedelta(seconds=30))))
    mut("window_end_before_start", lambda b: b["window"].update(end=iso(T0 - timedelta(minutes=5))))
    mut("objective_one", lambda b: b["slo"].update(objective=1))
    mut("unknown_event_kind", lambda b: b["events"].append({"id": "z", "at": iso(T0), "kind": "explode"}))
    mut("bool_counts", lambda b: b["telemetry"][0].update(good=True, total=True))
    b, per = bundle(seed=19); rc, rep, _ = run(b, "e13-ok")
    row("E13_invalid_refused_then_recovers", all(v == 2 for v in res.values()) and rc == 0, dict(res, valid_after=rc))
def e14():  # zero-traffic minutes and odd timestamps (doc silent: recorded)
    b, per = bundle(seed=20, traffic=lambda i: 0 if i in (5, 6) else 1000, change_min=80); rc, rep, _ = run(b, "e14a")
    per2 = {i: v for i, v in per.items()}; exp = expect(per2, "0.995"); ok, diff = slo_ok(rep, exp)
    row("E14_zero_traffic_minutes", True, {"rc": rc, "values_match_request_weighted": ok, "measured_minutes": (rep or {}).get("slo", {}).get("measured_minutes"), "coverage": (rep or {}).get("slo", {}).get("coverage")}, obs=True)
    b, per = bundle(seed=21, change_min=80); b["telemetry"][3]["minute"] = b["telemetry"][3]["minute"].replace(":00Z", ":30Z"); rc2, _, _ = run(b, "e14b")
    b, per = bundle(seed=22, change_min=80); b["events"] = [{"id": "tz", "at": "2026-09-07T15:10:00+02:00", "kind": "note"}]; rc3, rep3, _ = run(b, "e14c")
    row("E14b_odd_timestamps", True, {"telemetry_minute_with_seconds_rc": rc2, "event_with_offset_rc": rc3, "event_at_in_timeline": [x.get("at") for x in (rep3 or {}).get("timeline", []) if x.get("id") == "tz"]}, obs=True)
def e15():  # no write except --out; bundle folder byte-identical
    b, per = bundle(seed=23); d = TOP / "e15"; d.mkdir(); p = d / "b.json"; p.write_text(json.dumps(b)); before = {x.name: x.read_bytes() for x in d.iterdir()}
    subprocess.run([PY, str(TOOL), "report", str(p), "--json"], cwd=d, env=ENV, capture_output=True); after = {x.name: x.read_bytes() for x in d.iterdir()}
    row("E15_reads_only", before == after, {"files_after": sorted(after)})
def e16():  # G10 trace: dns fault during impact blocks code rollback; before the impact does not; path outside bundle refused
    tr = json.loads((REPO / "examples/capabilities/G11/fixtures/traces/dns-nxdomain-0930.json").read_text())
    res = {}
    for name, cap in (("during", 40), ("before", 10)):
        b, per = bundle(seed=24, bad=lambda i, t: (t // 6 if 33 <= i < 50 else 0)); d = TOP / ("e16" + name); d.mkdir(); t = dict(tr, captured_at=iso(T0 + timedelta(minutes=cap)))
        (d / "t.json").write_text(json.dumps(t)); b["diagnoses"] = ["t.json"]; p = d / "bundle.json"; p.write_text(json.dumps(b))
        cp = subprocess.run([PY, str(TOOL), "report", str(p), "--json"], cwd=d, env=ENV, capture_output=True, text=True); res[name] = (cp.returncode, json.loads(cp.stdout).get("decision", {}).get("decision") if cp.returncode == 0 else None)
    b, per = bundle(seed=24); d = TOP / "e16out"; d.mkdir(); (TOP / "outside.json").write_text(json.dumps(tr)); b["diagnoses"] = ["../outside.json"]; p = d / "bundle.json"; p.write_text(json.dumps(b))
    res["outside_path_rc"] = subprocess.run([PY, str(TOOL), "report", str(p), "--json"], cwd=d, env=ENV, capture_output=True).returncode
    row("E16_g10_trace_gating", res["during"] == (0, "do_not_rollback") and res["before"] == (0, "rollback") and res["outside_path_rc"] == 2, res)
def e17():  # all-zero traffic: no crash (rc 0 or 2, no traceback); window over 31 days refused
    b, per = bundle(seed=25, traffic=lambda i: 0, bad=lambda i, t: 0); d = TOP / "e17"; d.mkdir(); p = d / "b.json"; p.write_text(json.dumps(b))
    cp = subprocess.run([PY, str(TOOL), "report", str(p), "--json"], cwd=d, env=ENV, capture_output=True, text=True)
    st = json.loads(cp.stdout).get("slo", {}).get("status") if cp.returncode == 0 else None
    b2, _ = bundle(seed=26, n=10); b2["window"]["end"] = iso(T0 + timedelta(days=31, minutes=1)); rc2, _, _ = run(b2, "e17b")
    row("E17_zero_denominator_and_window_limit", cp.returncode in (0, 2) and "Traceback" not in cp.stderr and st != "met" and rc2 == 2, {"zero_rc": cp.returncode, "zero_status": st, "stderr_tail": cp.stderr[-200:], "window_32d_rc": rc2})
def e18():  # burn rate from the change: whether the change minute counts (doc says "from the change"); recorded
    b, per = bundle(seed=27, bad=lambda i, t: (t // 6 if 33 <= i < 40 else 0)); rc, rep, _ = run(b, "e18")
    tr = [x for x in (rep or {}).get("decision", {}).get("trace", []) if "burn" in json.dumps(x)]
    row("E18_burn_since_change_window", True, {"trace": tr}, obs=True)
for rid, fn in (("E16", e16), ("E17", e17), ("E18", e18), ("E01", e01), ("E02", e02), ("E03", e03), ("E04", e04), ("E05", e05), ("E06", e06), ("E07", e07), ("E08", e08), ("E09", e09), ("E10", e10), ("E11", e11), ("E12", e12), ("E13", e13), ("E14", e14), ("E15", e15)):
    guard(rid, fn)
shutil.rmtree(TOP, ignore_errors=True)
json.dump(rows, open(OUT, "w"), indent=1, default=str)
core = [r for r in rows if r["kind"] == "core"]
for r in rows: print(r["id"], r["result"], json.dumps(r["detail"], default=str)[:500])
print("M11 ORACLE %d/%d core PASS" % (sum(r["result"] == "PASS" for r in core), len(core)))
