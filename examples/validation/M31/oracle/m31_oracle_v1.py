#!/usr/bin/env python3
"""M31 oracle (Grok self-validation, not independent review). Written from M31.md, G31.md and
scope-estimate-acceptance.md before reading the builder's oracle. Each case copies the fixture folder to a temp
dir, edits portal.json or delivery.json, runs the tool and checks exit code, status and the finding codes the
doc names. Estimates are recomputed here with Decimal (sum of in-scope low/likely/high; price = hours x rate,
half up to cents).
Authoring fixes after the first run (kept in results/kept, 9/11), disclosed: K09 a deleted evidence file may be
reported as missing_evidence or evidence_mismatch (the doc lists both for "whose evidence file still matches"); K11
my generator could make low > likely (an invalid package, exit 2), now likely >= low + 1.
Usage: PY m31_oracle.py SRC OUT.json [--tool PATH]. Output rows: {row, pass, detail}."""
import copy, hashlib, json, os, random, shutil, subprocess, sys, tempfile
from decimal import Decimal, ROUND_HALF_UP
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(SRC, "employees/product-project/business-analyst/scope_acceptance.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
FIX = os.path.join(SRC, "examples/capabilities/G31/fixtures"); PY = sys.executable
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
BASE = json.load(open(os.path.join(FIX, "portal.json"))); DBASE = json.load(open(os.path.join(FIX, "delivery.json")))
ROWS = []

class Pkg:
    def __init__(s):
        s.top = tempfile.mkdtemp(prefix="m31o-"); s.d = os.path.join(s.top, "f"); shutil.copytree(FIX, s.d)
        s.p = copy.deepcopy(BASE); s.dl = copy.deepcopy(DBASE)
    def write(s):
        json.dump(s.p, open(os.path.join(s.d, "portal.json"), "w"), indent=1); json.dump(s.dl, open(os.path.join(s.d, "delivery.json"), "w"), indent=1)
    def run(s, *a):
        s.write(); r = subprocess.run([PY, TOOL] + [x.replace("@P", os.path.join(s.d, "portal.json")).replace("@D", os.path.join(s.d, "delivery.json")).replace("@", s.d + "/") for x in a],
                                      cwd=s.top, env=ENV, capture_output=True, text=True, timeout=120)
        try: j = json.loads(r.stdout)
        except Exception: j = {}
        return r.returncode, j, r.stdout + r.stderr
    def check(s): return s.run("check", "@P", "--json")
    def accept(s): return s.run("accept", "@P", "@D", "--json")
    def close(s): shutil.rmtree(s.top, ignore_errors=True)
    def req(s, rid): return next(r for r in s.p["requirements"] if r["id"] == rid)

def codes(j):
    out = []
    for f in j.get("findings", []) or []:
        out.append(f.get("code") if isinstance(f, dict) else str(f))
    return sorted(set(out))

def row(name, ok, det): ROWS.append({"row": name, "pass": bool(ok), "detail": det}); print(("PASS " if ok else "FAIL ") + name + " " + json.dumps(det, default=str)[:420], flush=True)

def case(edit, want, kind="check"):
    """edit(pkg) then run; want = code that must be present (None = must be ready/accepted with no findings)."""
    k = Pkg()
    try:
        edit(k); rc, j, raw = k.check() if kind == "check" else k.accept(); cs = codes(j)
    except Exception as e:
        k.close(); return False, {"crash": repr(e)}
    k.close()
    if want is None: return rc == 0 and cs == [], {"rc": rc, "codes": cs, "status": j.get("status")}
    return rc == 1 and want in cs, {"rc": rc, "codes": cs, "status": j.get("status")}

def D(x): return Decimal(str(x))
def money(x): return str(D(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + " crash", False, {"crash": repr(e)})
    return g

@safe
def k01():
    k = Pkg(); rc, j, _ = k.check(); sc = BASE["proposal"]["scope"]; rs = [r for r in BASE["requirements"] if r["id"] in sc]
    h = {t: sum(D(r["estimate_hours"][t]) for r in rs) for t in ("low", "likely", "high")}; rate = D(BASE["rate"]["per_hour"])
    est = j.get("estimate", {}); ok = rc == 0 and j.get("status") == "ready" and codes(j) == [] and {t: D(est.get("hours", {}).get(t, "-1")) for t in h} == h \
        and D(est.get("price", {}).get("low", "-1")) == D(money(h["low"] * rate)) and D(est.get("price", {}).get("high", "-1")) == D(money(h["high"] * rate)) and j.get("conditions") == ["A2"]
    ra, ja, _ = k.accept(); k.close()
    row("K01 clean control: ready, hours and price reconcile with an independent Decimal sum, A2 a condition; delivery accepted", ok and ra == 0, {"rc": rc, "est": est, "mine": {t: str(v) for t, v in h.items()}, "accept_rc": ra})

@safe
def k02():
    res = {}
    def add(cm):
        return lambda k: k.p["proposal"]["commitments"].append(cm)
    res["sla_no_refs"] = case(add({"id": "C9", "kind": "sla", "text": "99.99% uptime", "refs": []}), "invented_commitment")
    res["unknown_ref"] = case(add({"id": "C9", "kind": "other", "text": "free training", "refs": ["R99"]}), "invented_commitment")
    res["sla_input_only"] = case(add({"id": "C9", "kind": "sla", "text": "support 24/7", "refs": ["IN1"]}), "invented_commitment")
    res["feature_input_only"] = case(add({"id": "C9", "kind": "feature", "text": "a mobile app", "refs": ["IN2"]}), "invented_commitment")
    res["out_of_scope_R5"] = case(add({"id": "C9", "kind": "feature", "text": "board reports", "refs": ["R5"]}), "out_of_scope_commitment")
    row("K02 invented and out-of-scope commitments block", all(v[0] for v in res.values()), res)

@safe
def k03():
    res = {}
    res["untraced_empty"] = case(lambda k: k.req("R3").__setitem__("traces", []), "untraced_requirement")
    res["untraced_unknown"] = case(lambda k: k.req("R3").__setitem__("traces", ["IN99"]), "untraced_requirement")
    res["missing_dependency"] = case(lambda k: k.req("R2").__setitem__("depends_on", ["R1", "R5"]), "missing_dependency")
    def silent(k): k.req("R5").pop("optional", None); k.p["proposal"]["exclusions"] = []
    res["silent_exclusion"] = case(silent, "silent_exclusion")
    def opt_ok(k): k.p["proposal"]["exclusions"] = []
    res["optional_not_listed_ok"] = case(opt_ok, None)
    res["no_acceptance"] = case(lambda k: k.req("R4").__setitem__("acceptance", []), "no_acceptance_criteria")
    row("K03 traceability: untraced, missing dependency, silent exclusion, no acceptance criteria; an optional unlisted requirement is fine", all(v[0] for v in res.values()), res)

@safe
def k04():
    res = {}
    def demo_changed(k): open(os.path.join(k.d, "demos/CAP-sms.json"), "a").write(" ")
    def demo_rec(field, val):
        def f(k):
            p = os.path.join(k.d, "demos/CAP-sms.json"); r = json.load(open(p)); r[field] = val; b = json.dumps(r).encode(); open(p, "wb").write(b)
            next(c for c in k.p["capabilities"] if c["id"] == "CAP-sms")["demo"]["sha256"] = hashlib.sha256(b).hexdigest()
        return f
    res["demo_file_changed"] = case(demo_changed, "undemonstrated_capability")
    res["demo_missing"] = case(lambda k: os.remove(os.path.join(k.d, "demos/CAP-sms.json")), "undemonstrated_capability")
    res["demo_failed_exit"] = case(demo_rec("exit_code", 1), "undemonstrated_capability")
    res["demo_result_fail"] = case(demo_rec("result", "fail"), "undemonstrated_capability")
    res["demo_after_as_of"] = case(demo_rec("ran_at", "2026-10-07T09:00:00Z"), "undemonstrated_capability")
    res["demo_other_capability"] = case(demo_rec("capability", "CAP-booking"), "undemonstrated_capability")
    res["no_capability"] = case(lambda k: k.req("R3").__setitem__("capability", None), "undemonstrated_capability")
    res["resigned_pass_ok"] = case(demo_rec("result", "pass"), None)
    row("K04 demo evidence: changed, missing, failing, late, wrong capability, none; a re-pinned passing record is fine", all(v[0] for v in res.values()), res)

@safe
def k05():
    res = {}
    res["vague_seamless"] = case(lambda k: k.req("R3").__setitem__("text", "Seamless reminder text 24 hours before each appointment"), "unescalated_ambiguity")
    res["vague_in_criterion"] = case(lambda k: k.req("R4")["acceptance"][0].__setitem__("criterion", "import is fast"), "unescalated_ambiguity")
    res["vague_tbd"] = case(lambda k: k.req("R1").__setitem__("text", "Online booking, TBD channels"), "unescalated_ambiguity")
    res["no_measure"] = case(lambda k: k.req("R4")["acceptance"][0].__setitem__("measure", ""), "unescalated_ambiguity")
    res["breakfast_not_vague"] = case(lambda k: k.req("R3").__setitem__("text", "Reminder text 24 hours before each breakfast appointment"), None)
    def escalated(k):
        k.req("R3")["text"] = "Seamless reminder text 24 hours before each appointment"
        k.p["ambiguities"].append({"id": "AMB9", "about": ["R3"], "question": "what is seamless?", "escalated_to": "Clinic operations manager", "status": "resolved",
                                   "resolution": {"text": "no extra step for the patient", "source": "call notes 2026-10-01", "date": "2026-10-01"}})
    res["vague_resolved_ok"] = case(escalated, None)
    def opened(k): k.p["ambiguities"][0]["status"] = "open"; k.p["ambiguities"][0].pop("resolution", None)
    ok_o, det_o = case(opened, "open_ambiguity"); k = Pkg(); opened(k); rc, j, _ = k.check(); k.close()
    res["open_ambiguity"] = (ok_o and "commitment_on_blocked_requirement" in codes(j) and bool(j.get("escalations")), {"codes": codes(j), "escalations": j.get("escalations")})
    row("K05 ambiguity: vague words and missing measures need an escalation; an open one blocks and is listed with its owner; no false hit on 'breakfast'", all(v[0] for v in res.values()), res)

@safe
def k06():
    res = {}
    res["hours_off_by_one"] = case(lambda k: k.p["proposal"]["estimate"]["hours"].__setitem__("high", "441"), "estimate_mismatch")
    res["price_off_by_cent"] = case(lambda k: k.p["proposal"]["estimate"]["price"].__setitem__("high", "66000.01"), "estimate_mismatch")
    def rate_half(price_low):
        def f(k):
            k.p["rate"]["per_hour"] = "0.0375"; k.p["proposal"]["estimate"]["price"] = {"low": price_low, "high": money(D(440) * D("0.0375"))}
        return f
    res["half_up_8.63_ok"] = case(rate_half("8.63"), None)
    res["half_even_8.62_mismatch"] = case(rate_half("8.62"), "estimate_mismatch")
    def drop_r4_from_scope_keep_hours(k):
        k.p["proposal"]["scope"] = ["R1", "R2", "R3"]; k.p["proposal"]["exclusions"] = ["R4", "R5"]
        for c in k.p["proposal"]["commitments"]: c["refs"] = [r for r in c["refs"] if r != "R4"]
    res["scope_shrunk_hours_stale"] = case(drop_r4_from_scope_keep_hours, "estimate_mismatch")
    def fixed(hours, price, confirm=False):
        def f(k):
            k.p["proposal"]["estimate"] = {"type": "fixed", "hours": hours, "price": price}
            if confirm: k.p["assumptions"][1]["confirmed"] = True
        return f
    res["fixed_on_unconfirmed"] = case(fixed("440", "66000.00"), "unsupported_fixed_estimate")
    res["fixed_confirmed_ok"] = case(fixed("440", "66000.00", True), None)
    res["fixed_below_high"] = case(fixed("439", "65850.00", True), "unsupported_fixed_estimate")
    def fixed_open(k): fixed("440", "66000.00", True)(k); k.p["ambiguities"][0]["status"] = "open"; k.p["ambiguities"][0].pop("resolution", None)
    res["fixed_with_open_ambiguity"] = case(fixed_open, "unsupported_fixed_estimate")
    row("K06 estimates: exact sums, half-up cents, stale hours after a scope change; fixed estimates only at the high sum, confirmed, no open ambiguity", all(v[0] for v in res.values()), res)

@safe
def k07():
    res = {}
    def date(v): return lambda k: next(c for c in k.p["proposal"]["commitments"] if c["kind"] == "date").__setitem__("value", v)
    res["before_downside_finish"] = case(date("2027-02-06"), "unsupported_date")
    res["on_downside_finish_ok"] = case(date("2027-02-07"), None)
    res["no_capacity"] = case(lambda k: k.p.pop("capacity"), "unsupported_date")
    def edit_result(k):
        p = os.path.join(k.d, "capacity/studio-result.json"); s = open(p).read(); j = json.loads(s)
        def bump(x):
            if isinstance(x, dict):
                for kk, v in x.items():
                    if isinstance(v, int) and not isinstance(v, bool) and "week" in kk: x[kk] = v - 2; return True
                    if bump(v): return True
            if isinstance(x, list):
                for v in x:
                    if bump(v): return True
            return False
        bump(j); open(p, "w").write(json.dumps(j))
    res["stored_result_edited"] = case(edit_result, "unsupported_date")
    res["infeasible_option"] = case(lambda k: k.p["capacity"].__setitem__("option", "as-is"), "unsupported_date")
    row("K07 dates: downside finish boundary (2027-02-07 ok, 02-06 blocked), no capacity, an edited stored G17 result, an infeasible option", all(v[0] for v in res.values()), res)

@safe
def k08():
    res = {}
    def late(k): k.p["inputs"][0]["date"] = "2026-10-07"
    k = Pkg(); late(k); rc, j, _ = k.check(); k.close(); res["input_after_as_of"] = (rc in (1, 2) and j.get("status") != "ready", {"rc": rc})
    k = Pkg(); k.p["proposal"]["commitments"][0]["kind"] = "promise"; rc, j, _ = k.check(); k.close(); res["unknown_kind"] = (rc in (1, 2) and j.get("status") != "ready", {"rc": rc})
    k = Pkg(); k.p["proposal"]["estimate"]["hours"]["high"] = 440.0; rc, j, _ = k.check(); k.close(); res["float_hours"] = (rc in (1, 2) and j.get("status") != "ready", {"rc": rc})
    row("K08 invalid or late input is never ready", all(v[0] for v in res.values()), res)

@safe
def k09():
    res = {}
    def ev_changed(k): open(os.path.join(k.d, "evidence/AC3.txt"), "a").write("x")
    res["evidence_mismatch"] = case(ev_changed, "evidence_mismatch", "accept")
    res["criterion_failed"] = case(lambda k: k.dl["results"][1].__setitem__("outcome", "fail"), "criterion_failed", "accept")
    res["missing_evidence"] = case(lambda k: k.dl["results"].pop(4), "missing_evidence", "accept")
    ok_g, det_g = case(lambda k: os.remove(os.path.join(k.d, "evidence/AC1.txt")), "missing_evidence", "accept")
    res["evidence_file_gone"] = (det_g.get("rc") == 1 and bool({"missing_evidence", "evidence_mismatch"} & set(det_g.get("codes", []))), det_g)
    res["scope_not_ready"] = case(lambda k: k.req("R3").__setitem__("traces", []), "scope_not_ready", "accept")
    for nm, ed in (("unknown_criterion", lambda k: k.dl["results"].append(dict(k.dl["results"][0], criterion="AC99"))),
                   ("repeated_criterion", lambda k: k.dl["results"].append(dict(k.dl["results"][0]))),
                   ("result_after_as_of", lambda k: k.dl["results"][0].__setitem__("date", "2027-02-09"))):
        k = Pkg(); ed(k); rc, j, _ = k.accept(); k.close(); res[nm] = (rc in ((2,) if nm != "result_after_as_of" else (1, 2)), {"rc": rc})
    row("K09 acceptance: changed or missing evidence, a failed criterion, a blocked scope; unknown or repeated criteria invalid; a late result never accepts", all(v[0] for v in res.values()), res)

@safe
def k10():
    k = Pkg(); out = os.path.join(k.d, "res.json"); r1 = k.run("check", "@P", "--out", out)[0]; good = open(out).read()
    v0 = k.run("verify", out, "@P")[0]
    r_over = k.run("check", "@P", "--out", "@P")[0]; pkg_same = json.load(open(os.path.join(k.d, "portal.json"))) == k.p
    k.req("R3")["traces"] = []; r_bad = k.run("check", "@P", "--out", out)[0]; after_block = open(out).read()
    k.req("R3")["traces"] = ["IN3"]
    open(os.path.join(k.d, "portal.json"), "w").write("{broken"); k.p_write_skip = True
    r_inv = subprocess.run([PY, TOOL, "check", os.path.join(k.d, "portal.json"), "--out", out], cwd=k.top, env=ENV, capture_output=True, text=True).returncode
    kept = open(out).read() == after_block
    k.write(); r2 = k.run("check", "@P", "--out", out)[0]; j = json.loads(open(out).read()); j["status"] = "blocked"; open(out, "w").write(json.dumps(j))
    v1 = k.run("verify", out, "@P")[0]; open(out, "w").write(good[: len(good) // 2]); v2 = k.run("verify", out, "@P")[0]
    k.close()
    ok = r1 == 0 and v0 == 0 and r_over == 2 and pkg_same and r_bad == 1 and r_inv == 2 and kept and r2 == 0 and v1 == 1 and v2 in (1, 2)
    row("K10 recovery: --out refuses the package path, an invalid run keeps the earlier result, verify names an edited or truncated result", ok,
        {"check_out": r1, "verify_clean": v0, "out_over_package": r_over, "package_unchanged": pkg_same, "blocked_rc": r_bad, "invalid_rc": r_inv, "earlier_kept": kept, "verify_edited": v1, "verify_truncated": v2})

@safe
def k11():
    """Seeded soak: random in-scope subsets and estimates; correct totals are ready, a one-cent or one-hour error is a mismatch."""
    rnd = random.Random(3131); bad = []
    for i in range(12):
        k = Pkg(); ids = ["R1", "R2", "R3", "R4"]
        for r in k.p["requirements"][:4]:
            lo = rnd.randint(1, 90); li = lo + 1 + rnd.randint(0, 40); hi = li + rnd.randint(0, 60)
            r["estimate_hours"] = {"low": str(lo) + rnd.choice(["", ".5", ".25"]), "likely": str(li), "high": str(hi) + rnd.choice(["", ".75"])}
        rate = D(rnd.choice(["150.00", "97.35", "123.45", "88.88"])); k.p["rate"]["per_hour"] = str(rate)
        h = {t: sum(D(r["estimate_hours"][t]) for r in k.p["requirements"][:4]) for t in ("low", "likely", "high")}
        k.p["proposal"]["estimate"] = {"type": "range", "hours": {t: str(v) for t, v in h.items()}, "price": {"low": money(h["low"] * rate), "high": money(h["high"] * rate)}}
        rc0, j0, _ = k.check()
        k.p["proposal"]["estimate"]["price"]["low"] = money(D(k.p["proposal"]["estimate"]["price"]["low"]) + D("0.01")); rc1, j1, _ = k.check()
        k.close()
        if not (rc0 == 0 and rc1 == 1 and "estimate_mismatch" in codes(j1)): bad.append({"i": i, "rc0": rc0, "codes0": codes(j0), "rc1": rc1, "codes1": codes(j1), "h": {t: str(v) for t, v in h.items()}, "rate": str(rate)})
    row("K11 seeded soak: 12 random estimate sets reconcile exactly; one cent off is a mismatch", not bad, {"bad": bad[:3]})

@safe
def o12():
    """OBS (M31 goal: contradictory-requirement variant). Two in-scope requirements that contradict each other."""
    k = Pkg()
    k.p["inputs"].append({"id": "IN9", "text": "Booking must be closed outside office hours", "source": "ops email 2026-10-02", "date": "2026-10-02"})
    k.p["requirements"].append({"id": "R6", "text": "Booking closed outside office hours (08:00 to 18:00)", "traces": ["IN9"], "depends_on": ["R1"], "capability": "CAP-booking",
                                "estimate_hours": {"low": "4", "likely": "6", "high": "8"}, "acceptance": [{"id": "AC6", "criterion": "a booking at 19:00 is refused", "measure": "3 of 3 out-of-hours attempts refused"}]})
    k.req("R1")["text"] = "Online booking, moving and cancelling of appointments at any hour, 24/7"
    k.p["proposal"]["scope"].append("R6"); est = k.p["proposal"]["estimate"]
    for t, add in (("low", 4), ("likely", 6), ("high", 8)): est["hours"][t] = str(D(est["hours"][t]) + add)
    est["price"] = {"low": money(D(est["hours"]["low"]) * D("150")), "high": money(D(est["hours"]["high"]) * D("150"))}
    k.p["proposal"]["commitments"][0]["refs"].append("R6"); k.p["proposal"]["commitments"][1]["refs"].append("R6")
    rc, j, _ = k.check(); k.close()
    ROWS.append({"row": "O12 contradictory requirements (OBS)", "pass": True, "obs": True, "detail": {"rc": rc, "status": j.get("status"), "codes": codes(j)}})
    print("OBS O12", rc, j.get("status"), codes(j))

for f in (k01, k02, k03, k04, k05, k06, k07, k08, k09, k10, k11, o12): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
core = [r for r in ROWS if not r.get("obs")]; n = sum(r["pass"] for r in core)
print("M31 ORACLE %d/%d core %s" % (n, len(core), "PASS" if n == len(core) else "FAIL"))
