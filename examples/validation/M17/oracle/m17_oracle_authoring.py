#!/usr/bin/env python3
"""M17 oracle (Grok self-validation, not independent review; black box). Written from M17.md (independent scenario
variants and counterfactuals, infeasible capacity, contradictory stakeholder inputs; review computed consequences, not
prose) and resource-cash-decision.md. Packages are generated here; an independent week-by-week model of the documented
rules (priority list scheduling per role with max_people caps, start the week after dependencies, adverse bounds in
the downside, weekly cash = monthly x 12/52 exact, buffer = months x outflow in force, first week below it) gives the
expected finish weeks, feasibility, binding cause, cash figures and ordering. Priorities are distinct within a role so
the doc's order is unambiguous. Usage: PY m17_oracle.py REPO OUT.json [--tool TOOL.py]."""
import copy, hashlib, json, math, random, shutil, subprocess, sys, tempfile
from fractions import Fraction as Fr
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
REPO = Path(sys.argv[1]).resolve(); OUT = sys.argv[2]
TOOL = Path(sys.argv[sys.argv.index("--tool") + 1]).resolve() if "--tool" in sys.argv else REPO / "employees/leadership/coo/resource_decision.py"
TOP = Path(tempfile.mkdtemp(prefix="m17o-", dir="/tmp")).resolve(); ROWS = []; K = [0]
ENV = {"PATH": "/usr/bin:/bin", "HOME": str(TOP), "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C"}
def row(rid, ok, det, obs=False): ROWS.append({"id": rid, "kind": "OBS" if obs else "core", "result": "OBS" if obs else ("PASS" if ok else "FAIL"), "detail": det})
def cents(x): return str((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
ADV = {"hours": "high", "people": "low", "hpw": "low", "focus": "low", "start": "high", "ramp": "high", "opening": "low", "inflow": "low", "outflow": "high", "cost": "high", "extra": "high", "until": "low"}
class Pk:
    """Builder for packages plus the independent model's inputs (value, low, high per assumption)."""
    def __init__(self, weeks=20):
        self.A = {}; self.p = {"schema": "solaris.resource-decision/1", "decision": {"question": "synthetic M17 scenario", "owner": "COO (synthetic)", "as_of": "2026-10-05", "currency": "USD"},
                  "assumptions": {}, "calendar": {"start": "2026-10-05", "weeks": weeks}, "capacity": [], "work": [], "milestones": [], "cash": {}, "options": [], "risks": [], "dissent": []}
    def a(self, name, v, lo=None, hi=None, exact=False, downside=None, dated="2026-10-01"):
        d = {"value": v, "source": "synthetic M17", "dated": dated}
        if lo is not None: d["low"] = lo
        if hi is not None: d["high"] = hi
        if exact: d["exact"] = True
        if downside: d["downside"] = downside
        self.p["assumptions"][name] = d; return name
    def val(self, name, case, kind):
        d = self.p["assumptions"][name]; v = d["value"]
        if case == "downside":
            want = d.get("downside") or ADV[kind]; v = d.get(want, v)
        return Fr(str(v))
def model(P, opt, case):
    """Independent schedule and cash for one option and case. Returns finish weeks, milestones, cash."""
    pk = P; p = pk.p; W = p["calendar"]["weeks"]
    roles = {c["role"]: (pk.val(c["people"], case, "people"), pk.val(c["hours_per_week"], case, "hpw"), pk.val(c["focus"], case, "focus")) for c in p["capacity"]}
    work = {w["id"]: dict(w, h=pk.val(w["hours"], case, "hours")) for w in p["work"] if w["id"] not in opt.get("descope", [])}
    if case == "downside":
        for r in p["risks"]:
            if r.get("work") in work and r.get("extra_hours"): work[r["work"]]["h"] += pk.val(r["extra_hours"], case, "extra")
    rem = {k: v["h"] for k, v in work.items()}; fin = {}
    def cap(role, wk):
        n, h, f = roles[role]; c = n * h * f
        for a in opt.get("capacity_add", []):
            if a["role"] != role: continue
            s = pk.val(a["from_week"], case, "start"); rp = pk.val(a["ramp_weeks"], case, "ramp"); u = pk.val(a["until_week"], case, "until") if "until_week" in a else None
            if wk < s or (u is not None and wk > u): continue
            full = h * f * pk.val(a["people"], case, "people"); c += full / 2 if wk < s + rp else full
        return c
    for wk in range(1, W + 1):
        done_now = []
        for role in roles:
            c = cap(role, wk)
            ready = sorted([k for k, v in work.items() if v["role"] == role and k not in fin and all(d in fin and fin[d] < wk for d in v.get("after", []) if d in work)], key=lambda k: work[k]["priority"])
            for k in ready:
                if c <= 0: break
                lim = c
                if work[k].get("max_people"): n, h, f = roles[role]; lim = min(lim, work[k]["max_people"] * h * f)
                use = min(lim, rem[k]); rem[k] -= use; c -= use
                if rem[k] == 0: done_now.append(k)
        for k in done_now: fin[k] = wk
    shift = opt.get("deadline_shift_weeks", 0); ms = []
    for m in p["milestones"]:
        needs = [n for n in m["needs"] if n in work]; f = max([fin.get(n, 10 ** 6) for n in needs] or [0])
        ms.append({"id": m["id"], "deadline": m["deadline_week"] + shift, "finish": f if f < 10 ** 6 else None, "met": f <= m["deadline_week"] + shift})
    c = p["cash"]; bal = pk.val(c["opening"], case, "opening"); inflow = pk.val(c["monthly_inflow"], case, "inflow"); out = pk.val(c["monthly_outflow"], case, "outflow")
    buf_m = pk.val(c["min_buffer_months"], case, "people") ; mc = pk.val(opt["monthly_cost"], case, "cost") if opt.get("monthly_cost") else None
    cf = int(pk.val(opt["cost_from_week"], case, "start")) if opt.get("cost_from_week") else 1
    cu = int(pk.val(opt["cost_until_week"], case, "until")) if opt.get("cost_until_week") else W
    one = pk.val(opt["one_time_cost"], case, "cost") if opt.get("one_time_cost") else None
    riskc = sum((pk.val(r["cost"], case, "cost") for r in p["risks"] if r.get("cost")), Fr(0)) if case == "downside" else Fr(0)
    low = bal; breach = None
    for wk in range(1, W + 1):
        o = out + (mc if mc is not None and cf <= wk <= cu else 0)
        bal += (inflow - o) * Fr(12, 52)
        if one is not None and wk == cf: bal -= one
        if riskc and wk == 1: bal -= riskc
        if bal < low: low = bal
        if breach is None and bal < buf_m * o: breach = wk
    return {"fin": fin, "ms": ms, "closing": cents(bal), "lowest": cents(low), "breach": breach, "feasible": all(x["met"] for x in ms) and breach is None}
def run(P, *extra, fname="pkg.json", raw=None):
    K[0] += 1; d = TOP / ("p%03d" % K[0]); d.mkdir(); f = d / fname; f.write_text(raw if raw is not None else json.dumps(P.p, indent=1))
    before = sorted(x.name for x in d.iterdir()); h = hashlib.sha256(f.read_bytes()).hexdigest()
    cp = subprocess.run([sys.executable, str(TOOL), "evaluate", str(f), "--json"] + list(extra), cwd=str(d), env=ENV, capture_output=True, text=True, timeout=120)
    try: rep = json.loads(cp.stdout)
    except Exception: rep = None
    return cp.returncode, rep, d, f, h == hashlib.sha256(f.read_bytes()).hexdigest()
def opt_of(rep, oid): return next((o for o in (rep or {}).get("options", []) if o.get("id") == oid), {})
def compare(P, rep, oid, case):
    o = opt_of(rep, oid); c = (o.get("cases") or {}).get(case, {}); e = model(P, next(x for x in P.p["options"] if x["id"] == oid), case)
    got = {"fin": {k: v for k, v in (c.get("finish_weeks") or {}).items() if v is not None}, "closing": (c.get("cash") or {}).get("closing"), "lowest": (c.get("cash") or {}).get("lowest"),
           "breach": ((c.get("cash") or {}).get("buffer_breach") or {}).get("week"), "feasible": c.get("feasible")}
    want = {"fin": e["fin"], "closing": e["closing"], "lowest": e["lowest"], "breach": e["breach"], "feasible": e["feasible"]}
    return got == want, {"got": got, "want": want}
def base_pkg(weeks=20, be=2, hours=(400, None, 480), dl=8):
    P = Pk(weeks); P.a("be", be, exact=True); P.a("hpw", 40, lo=36); P.a("focus", "0.75", lo="0.6", hi="0.8")
    P.a("h_api", hours[0], hi=hours[2]); P.a("h_int", 80, hi=100); P.a("h_opt", 120, hi=140)
    P.a("open", 650000, lo=624000); P.a("in", 104000, lo=91000); P.a("burn", 117000, hi=130000); P.a("buf", 2, exact=True); P.a("zero", 0, exact=True)
    P.p["capacity"] = [{"role": "backend", "people": "be", "hours_per_week": "hpw", "focus": "focus"}]
    P.p["work"] = [{"id": "api", "role": "backend", "hours": "h_api", "priority": 1}, {"id": "integ", "role": "backend", "hours": "h_int", "after": ["api"], "priority": 2, "max_people": 2},
                   {"id": "opt", "role": "backend", "hours": "h_opt", "priority": 3}]
    P.p["milestones"] = [{"id": "launch", "needs": ["integ"], "deadline_week": dl}]
    P.p["cash"] = {"opening": "open", "monthly_inflow": "in", "monthly_outflow": "burn", "min_buffer_months": "buf"}
    P.p["options"] = [{"id": "as-is", "label": "as is", "reversible": True, "undo": {"weeks": "zero", "cost": "zero"}}]
    return P
def both(rid, P, extra_ok=lambda rep, rc: True, want_rc=None):
    rc, rep, d, f, same = run(P); res = {}; ok = rep is not None
    for o in P.p["options"]:
        for case in ("base", "downside"):
            k, det = compare(P, rep, o["id"], case); ok &= k; res["%s/%s" % (o["id"], case)] = det if not k else "ok"
    feas = [o["id"] for o in P.p["options"] if model(P, o, "downside")["feasible"]]
    w = want_rc if want_rc is not None else (0 if feas else 1)
    ok = ok and rc == w and same and extra_ok(rep, rc)
    row(rid, ok, {"rc": rc, "want_rc": w, "status": (rep or {}).get("status"), "feasible_in_downside": (rep or {}).get("feasible_in_downside"), "model_feasible": feas, "cases": res}); return rep
# Q01 clean control: feasible in both cases; certainty limit, owner and read-only stated; figures equal the model
P = base_pkg(dl=12)
both("Q01_clean_control", P, lambda rep, rc: rep.get("decision_owner") == "COO (synthetic)" and "not a forecast" in (rep.get("certainty") or "") and "nothing was sent" in (rep.get("read_only") or "") and rep.get("status") == "feasible_options")
# Q02 impossible schedule (capacity): downside needs (480+100) h at 2x36x0.6=43.2 h/week; deadline 8 -> rejected, cause capacity, short hours exact
P = base_pkg(dl=8); rep = both("Q02_infeasible_capacity_rejected", P)
m = ((opt_of(rep, "as-is").get("cases") or {}).get("downside") or {}).get("milestones", [{}])[0]
need = Fr(480 + 100); have = 2 * Fr(36) * Fr("0.6") * 8; short = need - have
row("Q02b_capacity_binding_and_short_hours", m.get("met") is False and str(m.get("binding", "")).startswith("capacity") and Fr(str((m.get("capacity_short_hours") or {}).get("backend", "nan").replace("nan", "-1"))) == short,
    {"binding": m.get("binding"), "short": (m.get("capacity_short_hours") or {}), "want_short": str(float(short))})
e = model(P, P.p["options"][0], "downside"); nar = opt_of(rep, "as-is").get("narrowed") or {}
row("Q02c_narrowed_earliest_week", (nar.get("earliest_milestone_weeks") or {}).get("launch") == e["ms"][0]["finish"] and nar.get("drop_optional_work") in ([], None), {"narrowed": nar, "model_finish": e["ms"][0]["finish"]})
# Q03 dependency bound: a chain of 5 items each capped at 1 person, 40 h each; with 10 people it still needs 5 x ceil(40/(36*0.6)) weeks
P = base_pkg(dl=6); P.a("ten", 10, exact=True); P.p["capacity"][0]["people"] = "ten"; P.a("h40", 40, exact=True)
P.p["work"] = [{"id": "c%d" % i, "role": "backend", "hours": "h40", "priority": i + 1, "max_people": 1, "after": (["c%d" % (i - 1)] if i else [])} for i in range(5)]
P.p["milestones"] = [{"id": "launch", "needs": ["c4"], "deadline_week": 6}]; rep = both("Q03_dependency_chain", P)
m = ((opt_of(rep, "as-is").get("cases") or {}).get("downside") or {}).get("milestones", [{}])[0]
row("Q03b_binding_is_dependencies", str(m.get("binding", "")).startswith("dependencies"), {"binding": m.get("binding")})
# Q04 sequencing and narrowing: optional work ahead in priority delays the milestone; dropping it makes it feasible
P = base_pkg(dl=9); P.p["work"][2]["priority"] = 0; P.p["work"][2]["hours"] = P.a("h_opt2", 300, hi=330)
rep = both("Q04_optional_first_delays", P); nar = opt_of(rep, "as-is").get("narrowed") or {}
P2 = copy.deepcopy(P); P2.p["work"] = [w for w in P2.p["work"] if w["id"] != "opt"]; e2 = model(P2, P2.p["options"][0], "downside")
m = ((opt_of(rep, "as-is").get("cases") or {}).get("downside") or {}).get("milestones", [{}])[0]
row("Q04b_narrowing_drops_optional_work", nar.get("drop_optional_work") == ["opt"] and nar.get("feasible_downside") is e2["feasible"] and e2["feasible"] and not m.get("met"),
    {"narrowed": nar, "binding": m.get("binding"), "model_after_drop": e2["feasible"]})
row("O04c_cause_named", True, {"binding": m.get("binding")}, obs=True)
# Q05 cash breach: contractor option feasible on schedule but breaks the buffer; first breach week exact
P = base_pkg(dl=8); P.a("c2", 2, exact=True); P.a("cst", 3, hi=4, downside="high"); P.a("cr", 1, hi=2); P.a("ccost", 39000, hi=52000); P.a("cend", 12, exact=True); P.a("u", 2, exact=True); P.a("uc", 6500, exact=True)
P.p["options"].append({"id": "contractors", "label": "contractors", "capacity_add": [{"role": "backend", "people": "c2", "from_week": "cst", "ramp_weeks": "cr", "until_week": "cend"}],
                       "monthly_cost": "ccost", "cost_from_week": "cst", "cost_until_week": "cend", "reversible": True, "undo": {"weeks": "u", "cost": "uc"}})
P.a("open2", 300000, lo=280000); P.p["cash"]["opening"] = "open2"; rep = both("Q05_contractor_cash_breach", P)
# Q06 downside consistency: start week drives capacity AND cost from the same adverse figure (downside: high)
row("Q06_downside_one_world", compare(P, rep, "contractors", "downside")[0] and model(P, P.p["options"][1], "downside")["fin"] != model(P, P.p["options"][1], "base")["fin"], {"downside": compare(P, rep, "contractors", "downside")[1]})
# Q07 ordering: two reversible feasible and one irreversible feasible: reversible first, then highest lowest-cash
P = base_pkg(dl=14); P.a("one", 1, exact=True); P.a("c1", 1, exact=True); P.a("ccost2", 13000, exact=True); P.a("w2", 2, exact=True); P.a("fee", 26000, exact=True)
P.p["options"] += [{"id": "cheap-help", "label": "one contractor", "capacity_add": [{"role": "backend", "people": "c1", "from_week": "w2", "ramp_weeks": "one"}], "monthly_cost": "ccost2", "cost_from_week": "w2", "reversible": True, "undo": {"weeks": "one", "cost": "zero"}},
                   {"id": "perm-hire", "label": "hire", "capacity_add": [{"role": "backend", "people": "c1", "from_week": "w2", "ramp_weeks": "one"}], "one_time_cost": "fee", "monthly_cost": "ccost2", "cost_from_week": "w2", "reversible": False, "why_irreversible": "permanent offer"}]
rep = both("Q07a_three_feasible", P)
lows = {o["id"]: Fr(model(P, o, "downside")["lowest"]) for o in P.p["options"]}
want = sorted([o for o in P.p["options"] if o["reversible"]], key=lambda o: -lows[o["id"]]) + [o for o in P.p["options"] if not o["reversible"]]
row("Q07b_ordering_reversible_first_then_lowest_cash", (rep or {}).get("feasible_in_downside") == [o["id"] for o in want], {"got": (rep or {}).get("feasible_in_downside"), "want": [o["id"] for o in want], "lowest": {k: str(v) for k, v in lows.items()}})
# Q08 only an irreversible option survives: status says so, exit 0
P = base_pkg(dl=8); P.a("c4", 4, exact=True); P.a("w1", 1, exact=True); P.a("one", 1, exact=True); P.a("fee", 26000, exact=True); P.a("hc", 13000, exact=True)
P.p["options"].append({"id": "hire", "label": "hire", "capacity_add": [{"role": "backend", "people": "c4", "from_week": "w1", "ramp_weeks": "one"}], "one_time_cost": "fee", "monthly_cost": "hc", "cost_from_week": "w1", "reversible": False, "why_irreversible": "permanent"})
rep = both("Q08_irreversible_only", P, lambda rep, rc: rep.get("status") == "feasible_irreversible_only")
# Q09 risks realised in the downside: extra hours on a work item and a cost in week 1; exposure = probability x cost
P = base_pkg(dl=12); P.a("rp", "0.25", hi="0.5"); P.a("rx", 60, hi=90); P.a("rc", 26000, hi=39000)
P.p["risks"] = [{"id": "R1", "text": "rework", "owner": "lead", "mitigation": "tests", "probability": "rp", "work": "integ", "extra_hours": "rx", "cost": "rc", "applies_to": "all"}]
rep = both("Q09_risk_realised_in_downside", P)
ex = (opt_of(rep, "as-is").get("risk_exposure") or [{}])[0]
row("O09b_risk_exposure_figures", True, {"exposure": ex, "note": "doc: probabilities only weight the listed exposure"}, obs=True)
# Q10 contradictory stakeholder inputs and invalid packages: exit 2, nothing written
inv = {}
P = base_pkg(); P.p["assumptions"]["h_api"]["dated"] = "2026-11-01"; inv["dated_after_as_of"] = P
P = base_pkg(); P.p["work"][0]["hours"] = 400; inv["literal_number"] = P
P = base_pkg(); del P.p["decision"]["owner"]; inv["no_owner"] = P
P = base_pkg(); P.p["work"][0]["after"] = ["integ"]; inv["dependency_cycle"] = P
P = base_pkg(); P.p["work"][0]["hours"] = "nope"; inv["unknown_assumption"] = P
res = {}
for k, P in inv.items():
    rc, rep, d, f, same = run(P, "--out", "r.json"); res[k] = {"rc": rc, "out_written": (d / "r.json").exists()}
row("Q10_invalid_packages_exit2_nothing_written", all(v["rc"] == 2 and not v["out_written"] for v in res.values()), res)
P = base_pkg(); P.p["assumptions"]["h_api"].update({"low": 500, "value": 400, "high": 300}); rc, rep, _, _, _ = run(P)
row("O10b_low_above_high_contradiction", True, {"rc": rc, "status": (rep or {}).get("status"), "required_evidence": (rep or {}).get("required_evidence")}, obs=True)
# Q11 dissent echoed; required_evidence lists unranged and stale figures
P = base_pkg(dl=12); P.p["dissent"] = ["Finance (synthetic): the inflow low case is too optimistic.", "Delivery (synthetic): prefers descoping."]
P.a("h_int", 80, dated="2026-01-02"); rep = both("Q11a_dissent_and_evidence_figures", P)
re_ = json.dumps((rep or {}).get("required_evidence")); 
row("Q11b_dissent_echoed_and_required_evidence", (rep or {}).get("dissent") == P.p["dissent"] and "h_int" in re_ and ("stale" in re_.lower() or "180" in re_), {"dissent": (rep or {}).get("dissent"), "required_evidence": (rep or {}).get("required_evidence")})
# Q12 verify: rerun equal -> 0; a tampered figure -> 1 with the difference listed; inputs unchanged
P = base_pkg(dl=12); rc, rep, d, f, same = run(P, "--out", "r.json")
v1 = subprocess.run([sys.executable, str(TOOL), "verify", str(f), str(d / "r.json")], cwd=str(d), env=ENV, capture_output=True, text=True)
r = json.loads((d / "r.json").read_text()); r["options"][0]["cases"]["downside"]["cash"]["closing"] = "1.00"; (d / "r2.json").write_text(json.dumps(r))
v2 = subprocess.run([sys.executable, str(TOOL), "verify", str(f), str(d / "r2.json")], cwd=str(d), env=ENV, capture_output=True, text=True)
row("Q12_verify_rerun_and_tamper", rc == 0 and v1.returncode == 0 and v2.returncode == 1 and "closing" in (v2.stdout + v2.stderr) and same, {"evaluate_rc": rc, "verify_rc": v1.returncode, "tampered_rc": v2.returncode, "tampered_out": (v2.stdout + v2.stderr)[-200:]})
# Q13 recovery: a rejected plan, then the owner adds a deadline-shift option of exactly the narrowed weeks -> feasible
P = base_pkg(dl=8); rc1, rep1, _, _, _ = run(P); earliest = ((opt_of(rep1, "as-is").get("narrowed") or {}).get("earliest_milestone_weeks") or {}).get("launch")
P.p["options"].append({"id": "shift", "label": "move launch", "deadline_shift_weeks": (earliest or 8) - 8, "reversible": True, "undo": {"weeks": "zero", "cost": "zero"}})
rc2, rep2, _, _, _ = run(P); P.p["options"][-1]["deadline_shift_weeks"] = max(0, (earliest or 8) - 9); rc3, rep3, _, _, _ = run(P)
row("Q13_recovery_shift_by_narrowed_weeks", rc1 == 1 and earliest is not None and rc2 == 0 and "shift" in (rep2 or {}).get("feasible_in_downside", []) and "shift" not in (rep3 or {}).get("feasible_in_downside", []),
    {"rc_rejected": rc1, "earliest": earliest, "rc_shifted": rc2, "one_week_short_feasible": (rep3 or {}).get("feasible_in_downside")})
# Q14 counterfactual boundary: deadline equal to the model's downside finish week is met; one week earlier is not
P = base_pkg(dl=30, weeks=30); f = model(P, P.p["options"][0], "downside")["ms"][0]["finish"]; out = {}
for dl in (f, f - 1):
    P.p["milestones"][0]["deadline_week"] = dl; rc, rep, _, _, _ = run(P); out[dl] = ((opt_of(rep, "as-is").get("cases") or {}).get("downside") or {}).get("feasible")
row("Q14_deadline_boundary", out.get(f) is True and out.get(f - 1) is False, {"finish": f, "feasible_by_deadline": out})
# Q15 G14 evidence: reconciled books feed inflow; unreconciled books block (exit 1, blocked_evidence)
fx = REPO / "examples/capabilities/G17/fixtures"; res = {}
for name in ("books-sept", "books-unreconciled"):
    P = base_pkg(dl=12); P.p["assumptions"]["in"] = {"from_g14": {"package": name + "/package.json", "measure": "monthly_net_cash"}, "low": 91000, "source": "G14", "dated": "2026-10-05"}
    K[0] += 1; d = TOP / ("g%03d" % K[0]); d.mkdir(); shutil.copytree(fx / name, d / name); (d / "pkg.json").write_text(json.dumps(P.p))
    cp = subprocess.run([sys.executable, str(TOOL), "evaluate", str(d / "pkg.json"), "--json"], cwd=str(d), env=ENV, capture_output=True, text=True)
    try: rep = json.loads(cp.stdout)
    except Exception: rep = None
    res[name] = {"rc": cp.returncode, "status": (rep or {}).get("status")}
row("Q15_g14_evidence_gate", res["books-sept"]["rc"] in (0, 1) and res["books-sept"]["status"] != "blocked_evidence" and res["books-unreconciled"]["rc"] == 1 and res["books-unreconciled"]["status"] == "blocked_evidence", res)
# Q16 property: 25 random two-role packages with dependencies across roles, random capacities and cash; all figures equal the model
rng = random.Random(1717); fails = []
for k in range(25):
    P = Pk(rng.choice([12, 20, 26])); P.a("b", rng.randint(1, 4), exact=True); P.a("f", rng.randint(1, 3), lo=1); P.a("hp", 40, lo=rng.choice([30, 36])); P.a("fo", "0.7", lo=rng.choice(["0.5", "0.6"]))
    P.p["capacity"] = [{"role": "be", "people": "b", "hours_per_week": "hp", "focus": "fo"}, {"role": "fe", "people": "f", "hours_per_week": "hp", "focus": "fo"}]
    ws = []
    for i in range(rng.randint(3, 6)):
        hv = rng.randint(4, 40) * 10; nm = P.a("h%d" % i, hv, hi=hv + rng.randint(0, 10) * 10); deps = rng.sample([w["id"] for w in ws], k=min(len(ws), rng.randint(0, 2)))
        w = {"id": "w%d" % i, "role": rng.choice(["be", "fe"]), "hours": nm, "priority": i + 1, "after": deps}
        if rng.random() < 0.4: w["max_people"] = rng.randint(1, 2)
        ws.append(w)
    P.p["work"] = ws; P.p["milestones"] = [{"id": "m1", "needs": [ws[-1]["id"]], "deadline_week": rng.randint(4, P.p["calendar"]["weeks"])}]
    P.a("op", rng.randint(20, 60) * 13000, lo=None); P.a("in", rng.randint(5, 10) * 13000, lo=rng.randint(3, 5) * 13000); P.a("bu", rng.randint(6, 10) * 13000, hi=rng.randint(10, 12) * 13000); P.a("bm", rng.choice([1, 2]), exact=True); P.a("z", 0, exact=True)
    P.p["cash"] = {"opening": "op", "monthly_inflow": "in", "monthly_outflow": "bu", "min_buffer_months": "bm"}
    P.p["options"] = [{"id": "as-is", "label": "as is", "reversible": True, "undo": {"weeks": "z", "cost": "z"}}]
    rc, rep, _, _, _ = run(P); bad = {}
    for case in ("base", "downside"):
        okc, det = compare(P, rep, "as-is", case)
        if not okc: bad[case] = det
    feas = model(P, P.p["options"][0], "downside")["feasible"]
    if bad or rc != (0 if feas else 1): fails.append({"case": k, "rc": rc, "bad": bad})
row("Q16_random_packages_property", not fails, {"cases": 25, "fails": fails[:2]})
shutil.rmtree(TOP, ignore_errors=True)
json.dump(ROWS, open(OUT, "w"), indent=1, sort_keys=True, default=str)
for x in ROWS: print(x["id"], x["result"], json.dumps(x["detail"], sort_keys=True, default=str)[:300])
c = [x for x in ROWS if x["kind"] == "core"]; print("M17 ORACLE %d/%d core PASS" % (sum(x["result"] == "PASS" for x in c), len(c)))
