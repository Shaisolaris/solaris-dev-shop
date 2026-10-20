#!/usr/bin/env python3
"""G31 oracle: scope, estimate and acceptance checks against fixtures, failure cases and seeded unseen
packages whose expected findings are known by construction (the generator records every flaw it plants and
the findings that flaw must cause). Usage: scope_oracle.py [--tool PATH] [--seed N]. Prints one line per
check and a final ACCEPTED n/n or REJECTED k/n line. Standard library only; works in a temporary folder."""
import argparse, copy, hashlib, json, os, random, shutil, subprocess, sys, tempfile
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIX = HERE / "fixtures"
TOOL = ROOT / "employees" / "product-project" / "business-analyst" / "scope_acceptance.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")


class Ctx:
    def __init__(self, tool):
        self.tool = tool
        self.tmp = Path(tempfile.mkdtemp(prefix="g31-oracle-"))
        self.n = 0

    def fresh(self):
        self.n += 1
        d = self.tmp / ("w%d" % self.n)
        shutil.copytree(str(FIX), str(d))
        return d

    def run(self, *args):
        if not Path(self.tool).is_file():
            return 127, "", "no tool"
        r = subprocess.run([sys.executable, str(self.tool)] + [str(a) for a in args], capture_output=True, text=True,
                           env=ENV, timeout=300)
        return r.returncode, r.stdout, r.stderr

    def check(self, d, pkg):
        p = d / "pkg.json"
        p.write_text(json.dumps(pkg, indent=1))
        rc, out, err = self.run("check", p, "--json")
        try:
            return rc, json.loads(out)
        except ValueError:
            return rc, None


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def codes(r):
    return set() if not r else {(f["code"], f["ref"]) for f in r.get("findings", [])}


def base():
    return json.loads((FIX / "portal.json").read_text())


def req(p, k):
    return [r for r in p["requirements"] if r["id"] == k][0]


def com(p, k):
    return [c for c in p["proposal"]["commitments"] if c["id"] == k][0]


def o1(c):
    d = c.fresh(); rc, r = c.check(d, base())
    ok = (rc == 0 and r and r["status"] == "ready" and not r["findings"] and r["estimate"]["hours"] == {"low": "230", "likely": "310", "high": "440"}
          and r["estimate"]["price"] == {"low": "34500.00", "high": "66000.00"} and r["conditions"] == ["A2"]
          and r["capacity_finish"] == "2027-02-07" and r["excluded"] == ["R5"])
    if ok:
        m = {x["commitment"]: x for x in r["trace_matrix"]}
        ok = m["C3"]["sources"] == ["A1", "A2", "IN1", "IN2", "IN3", "IN4"] and m["C4"]["sources"] == ["IN3"] and m["C1"]["conditional_on"] == ["A2"]
    return ok, "clean fixture ready with exact totals, trace matrix and G17 finish"


def o2(c):
    p = base(); p["proposal"]["commitments"].append({"id": "C9", "kind": "sla", "text": "99.9% uptime", "refs": []})
    rc1, r1 = c.check(c.fresh(), p)
    p = base(); p["proposal"]["commitments"].append({"id": "C9", "kind": "feature", "text": "Video visits", "refs": ["IN9"]})
    rc2, r2 = c.check(c.fresh(), p)
    p = base(); p["proposal"]["commitments"].append({"id": "C9", "kind": "feature", "text": "Board reports", "refs": ["R5"]})
    rc3, r3 = c.check(c.fresh(), p)
    ok = (rc1 == 1 and codes(r1) == {("invented_commitment", "C9")} and rc2 == 1 and ("invented_commitment", "C9") in codes(r2)
          and rc3 == 1 and ("out_of_scope_commitment", "C9") in codes(r3))
    return ok, "invented and out-of-scope commitments blocked"


def o3(c):
    p = base(); p["proposal"]["estimate"]["price"]["high"] = "65999.99"
    rc1, r1 = c.check(c.fresh(), p)
    p = base(); p["proposal"]["estimate"] = {"type": "fixed", "hours": "440", "price": "66000.00"}
    rc2, r2 = c.check(c.fresh(), p)
    p["assumptions"][1]["confirmed"] = True
    rc3, r3 = c.check(c.fresh(), p)
    p["proposal"]["estimate"] = {"type": "fixed", "hours": "400", "price": "60000.00"}
    rc4, r4 = c.check(c.fresh(), p)
    p = base(); req(p, "R3")["estimate_hours"]["likely"] = "41"
    rc5, r5 = c.check(c.fresh(), p)
    ok = (rc1 == 1 and codes(r1) == {("estimate_mismatch", "price.high")}
          and rc2 == 1 and codes(r2) == {("unsupported_fixed_estimate", "estimate"), ("unsupported_fixed_estimate", "C2")}
          and rc3 == 0 and r3["status"] == "ready" and rc4 == 1 and ("unsupported_fixed_estimate", "estimate") in codes(r4)
          and rc5 == 1 and codes(r5) == {("estimate_mismatch", "hours.likely")})
    return ok, "estimate reconciles to the cent; fixed price needs high bound and confirmed assumptions"


def o4(c):
    p = base(); req(p, "R3")["text"] += " via a seamless flow"
    rc1, r1 = c.check(c.fresh(), p)
    p = base(); p["ambiguities"].append({"id": "AMB2", "about": ["R4"], "question": "Which CSV format?", "escalated_to": "Clinic IT lead", "status": "open"})
    rc2, r2 = c.check(c.fresh(), p)
    p = base(); req(p, "R4")["acceptance"][0]["measure"] = ""
    rc3, r3 = c.check(c.fresh(), p)
    p = base(); p["ambiguities"] = []
    rc4, r4 = c.check(c.fresh(), p)
    want2 = {("open_ambiguity", "R4")} | {("commitment_on_blocked_requirement", k) for k in ("C1", "C2", "C3")}
    ok = (rc1 == 1 and ("unescalated_ambiguity", "R3") in codes(r1) and ("commitment_on_blocked_requirement", "C4") in codes(r1)
          and rc2 == 1 and codes(r2) == want2 and [e["id"] for e in r2["escalations"]] == ["AMB2"]
          and rc3 == 1 and ("unescalated_ambiguity", "R4") in codes(r3) and rc4 == 1 and ("unescalated_ambiguity", "R2") in codes(r4))
    return ok, "vague wording and unmeasured criteria escalated; open escalation blocks commitments"


def o5(c):
    res = []
    d = c.fresh(); (d / "demos" / "CAP-sms.json").write_text("{}"); res.append(c.check(d, base()))
    p = base(); p["capabilities"][3].pop("demo"); res.append(c.check(c.fresh(), p))
    d = c.fresh(); f = d / "demos" / "CAP-sms.json"; rec = json.loads(f.read_text()); rec["exit_code"] = 1; rec["result"] = "fail"
    f.write_text(json.dumps(rec)); p = base(); p["capabilities"][2]["demo"]["sha256"] = sha(f); res.append(c.check(d, p))
    d = c.fresh(); f = d / "demos" / "CAP-sms.json"; rec = json.loads(f.read_text()); rec["ran_at"] = "2026-12-01T09:00:00-08:00"
    f.write_text(json.dumps(rec)); p = base(); p["capabilities"][2]["demo"]["sha256"] = sha(f); res.append(c.check(d, p))
    p = base(); req(p, "R2")["capability"] = None; res.append(c.check(c.fresh(), p))
    want = [("R3",), ("R4",), ("R3",), ("R3",), ("R2",)]
    ok = all(rc == 1 and ("undemonstrated_capability", w[0]) in codes(r) for (rc, r), w in zip(res, want))
    return ok, "capability without passing, unchanged, dated demo evidence is not offered"


def o6(c):
    p = base(); com(p, "C3")["value"] = "2027-01-15"; rc1, r1 = c.check(c.fresh(), p)
    d = c.fresh(); f = d / "capacity" / "studio-result.json"; j = json.loads(f.read_text()); j["feasible_in_downside"] = ["as-is", "descope-reporting"]
    f.write_text(json.dumps(j)); rc2, r2 = c.check(d, base())
    p = base(); p["capacity"]["option"] = "as-is"; rc3, r3 = c.check(c.fresh(), p)
    p = base(); p.pop("capacity"); rc4, r4 = c.check(c.fresh(), p)
    p = base(); com(p, "C3")["value"] = "2027-02-07"; rc5, r5 = c.check(c.fresh(), p)
    ok = (all(rc == 1 and codes(r) == {("unsupported_date", "C3")} for rc, r in ((rc1, r1), (rc2, r2), (rc3, r3), (rc4, r4)))
          and rc5 == 0)
    return ok, "delivery date needs an identical G17 rerun with a feasible downside finish on or before it"


def o7(c):
    d = c.fresh(); out = []
    def acc(dd, pkg=None, dl=None):
        p = dd / "pkg.json"; p.write_text(json.dumps(pkg or base()))
        q = dd / "dl.json"; q.write_text(json.dumps(dl or json.loads((FIX / "delivery.json").read_text())))
        rc, o, e = c.run("accept", p, q, "--json")
        try:
            return rc, json.loads(o)
        except ValueError:
            return rc, None
    out.append(acc(d))
    dl = json.loads((FIX / "delivery.json").read_text()); dl["results"][3]["outcome"] = "fail"; out.append(acc(c.fresh(), dl=dl))
    dl = json.loads((FIX / "delivery.json").read_text()); dl["results"].pop(1); out.append(acc(c.fresh(), dl=dl))
    d2 = c.fresh(); (d2 / "evidence" / "AC5.txt").write_text("edited after the fact\n"); out.append(acc(d2))
    p = base(); com(p, "C3")["value"] = "2027-01-15"; out.append(acc(c.fresh(), pkg=p))
    (rc0, r0), (rc1, r1), (rc2, r2), (rc3, r3), (rc4, r4) = out
    ok = (rc0 == 0 and r0["status"] == "accepted" and rc1 == 1 and codes(r1) == {("criterion_failed", "AC4")}
          and [x["status"] for x in r1["requirements"]] == ["accepted", "accepted", "not_accepted", "accepted"]
          and rc2 == 1 and codes(r2) == {("missing_evidence", "AC2")} and rc3 == 1 and codes(r3) == {("evidence_mismatch", "AC5")}
          and rc4 == 1 and codes(r4) == {("scope_not_ready", "check")})
    return ok, "acceptance needs passing, unchanged evidence for every criterion of a ready scope"


def o8(c):
    bad = []
    p = base(); req(p, "R1")["depends_on"] = ["R3"]; bad.append(p)
    p = base(); req(p, "R1")["estimate_hours"]["low"] = 120; bad.append(p)
    p = base(); p["inputs"][0]["date"] = "2026-11-01"; bad.append(p)
    p = base(); req(p, "R2")["depends_on"] = ["R7"]; bad.append(p)
    p = base(); p["requirements"][1]["id"] = "R1"; bad.append(p)
    p = base(); p["schema"] = "other/1"; bad.append(p)
    p = base(); req(p, "R1")["estimate_hours"]["low"] = "300"; bad.append(p)
    p = base(); p["proposal"]["scope"].append("R1"); bad.append(p)
    p = base(); p["capabilities"][0]["demo"]["path"] = "../outside.json"; bad.append(p)
    p = base(); p["rate"]["per_hour"] = "0"; bad.append(p)
    p = base(); p["assumptions"][0].pop("confirmed"); bad.append(p)
    ok = True
    for p in bad:
        d = c.fresh(); before = sorted(x.name for x in d.rglob("*"))
        q = d / "pkg.json"; q.write_text(json.dumps(p)); o = d / "out.json"
        rc, out, err = c.run("check", q, "--out", o)
        ok = ok and rc == 2 and not o.exists() and "INVALID" in err
    d = c.fresh(); dl = json.loads((FIX / "delivery.json").read_text()); dl["results"][0]["criterion"] = "AC99"
    q = d / "dl.json"; q.write_text(json.dumps(dl)); (d / "pkg.json").write_text(json.dumps(base()))
    rc, _, _ = c.run("accept", d / "pkg.json", q); ok = ok and rc == 2
    return ok, "%d invalid packages and an unknown delivery criterion refused, nothing written" % len(bad)


def o9(c):
    d = c.fresh(); p = d / "pkg.json"; p.write_text(json.dumps(base())); o = d / "res.json"
    rc1, _, _ = c.run("check", p, "--out", o)
    rc2, out2, _ = c.run("verify", o, p)
    j = json.loads(o.read_text()); j["estimate"]["price"]["high"] = "60000.00"; t = d / "t.json"; t.write_text(json.dumps(j))
    rc3, out3, _ = c.run("verify", t, p)
    t.write_text(o.read_text()[:200]); rc4, _, _ = c.run("verify", t, p)
    rc5, _, _ = c.run("check", p, "--out", p)
    keep = o.read_bytes(); bad = d / "bad.json"; bad.write_text("{not json"); rc6, _, _ = c.run("check", bad, "--out", o)
    q = d / "dl.json"; q.write_text((FIX / "delivery.json").read_text()); oa = d / "acc.json"
    rc7, _, _ = c.run("accept", p, q, "--out", oa); rc8, out8, _ = c.run("verify", oa, p, q)
    ok = (rc1 == 0 and rc2 == 0 and "IDENTICAL" in out2 and rc3 == 1 and "DIFFERENT" in out3 and rc4 != 0 and rc5 == 2
          and json.loads(p.read_text())["schema"] == "solaris.scope-package/1" and rc6 == 2 and o.read_bytes() == keep
          and rc7 == 0 and rc8 == 0 and not [x for x in d.iterdir() if x.name.startswith(".g31-")])
    return ok, "--out and verify; tampered or truncated results detected; failed run keeps the earlier result"


# ---- seeded unseen packages with flaws planted by construction ----
WORDS = ["seamless", "real-time", "scalable", "intuitive", "as needed", "asap", "user-friendly", "optimal"]


def gen(rng, d, n, flaws):
    caps, reqs, inputs = [], [], []
    for i in range(n):
        inputs.append({"id": "NEED%d" % i, "text": "customer need %d" % i, "source": "rfp section %d" % i, "date": "2026-09-14"})
    for i in range(n):
        rec = {"capability": "CAP%d" % i, "command": "python3 demo.py %d" % i, "exit_code": 0, "result": "pass", "ran_at": "2026-09-30"}
        f = d / "demos" / ("CAP%d.json" % i); f.write_text(json.dumps(rec))
        caps.append({"id": "CAP%d" % i, "name": "capability %d" % i, "demo": {"path": "demos/CAP%d.json" % i, "sha256": sha(f)}})
        lo = rng.randint(1, 80) * Decimal("0.5"); li = lo + rng.randint(0, 40) * Decimal("0.25"); hi = li + rng.randint(0, 60) * Decimal("0.25")
        dep = ["R%d" % rng.randrange(i)] if i and rng.random() < 0.4 else []
        reqs.append({"id": "R%d" % i, "text": "deliver need %d" % i, "traces": ["NEED%d" % i], "depends_on": dep, "capability": "CAP%d" % i,
                     "estimate_hours": {"low": str(lo), "likely": str(li), "high": str(hi)},
                     "acceptance": [{"id": "AC%d" % i, "criterion": "need %d works" % i, "measure": "%d of %d cases pass" % (i + 1, i + 1)}]})
    p = base(); p["inputs"] = inputs + [p["inputs"][3]]; p["assumptions"] = [p["assumptions"][0]]; p["ambiguities"] = []
    p["capabilities"] = caps; p["requirements"] = reqs
    scope = ["R%d" % i for i in range(n)]
    coms = [{"id": "CS", "kind": "scope", "text": "all needs", "refs": list(scope)},
            {"id": "CE", "kind": "estimate", "text": "estimate", "refs": list(scope)},
            {"id": "CD", "kind": "date", "text": "date", "value": "2027-0%d-1%d" % (rng.randint(2, 9), rng.randint(0, 9)), "refs": ["IN4"] + scope}]
    for i in rng.sample(range(n), 8):
        coms.append({"id": "CF%d" % i, "kind": "feature", "text": "need %d" % i, "refs": ["R%d" % i]})
    if coms[2]["value"] < "2027-02-07":
        coms[2]["value"] = "2027-02-07"
    p["proposal"] = {"scope": scope, "exclusions": [], "estimate": {"type": "range"}, "commitments": coms}
    want = set()
    dependents = {}
    for r in reqs:
        for x in r["depends_on"]:
            dependents.setdefault(x, []).append(r["id"])
    used = set()

    def pick(cond=lambda k: True):
        for _ in range(500):
            k = "R%d" % rng.randrange(n)
            if k not in used and cond(k):
                used.add(k); return k
        return None

    def blocked(k):
        want.add(("commitment_on_blocked_requirement", "CS")); want.add(("commitment_on_blocked_requirement", "CE"))
        want.add(("commitment_on_blocked_requirement", "CD"))
        if "CF" + k[1:] in [x["id"] for x in coms]:
            want.add(("commitment_on_blocked_requirement", "CF" + k[1:]))
    R = {r["id"]: r for r in reqs}
    for f in flaws:
        if f == "untrace":
            k = pick(); R[k]["traces"] = []; want.add(("untraced_requirement", k)); blocked(k)
        elif f == "unknown_trace":
            k = pick(); R[k]["traces"] = ["IN-missing"]; want.add(("untraced_requirement", k)); blocked(k)
        elif f == "nodemo":
            k = pick(); caps[int(k[1:])].pop("demo"); want.add(("undemonstrated_capability", k)); blocked(k)
        elif f == "tamper":
            k = pick(); (d / "demos" / ("CAP%s.json" % k[1:])).write_text("{}"); want.add(("undemonstrated_capability", k)); blocked(k)
        elif f == "vague":
            k = pick(); R[k]["text"] += " with " + rng.choice(WORDS) + " handling"; want.add(("unescalated_ambiguity", k)); blocked(k)
        elif f == "open":
            k = pick(); p["ambiguities"].append({"id": "AMB" + k, "about": [k], "question": "what is meant?", "escalated_to": "customer lead", "status": "open"})
            want.add(("open_ambiguity", k)); blocked(k)
        elif f == "resolved":
            k = pick(); R[k]["text"] += " with " + rng.choice(WORDS) + " handling"
            p["ambiguities"].append({"id": "AMB" + k, "about": [k], "question": "what is meant?", "escalated_to": "customer lead", "status": "resolved",
                                     "resolution": {"text": "defined in call", "source": "call notes", "date": "2026-10-01"}})
        elif f == "noac":
            k = pick(); R[k]["acceptance"] = []; want.add(("no_acceptance_criteria", k))
        elif f == "invented":
            coms.append({"id": "CX", "kind": "sla", "text": "uptime promise", "refs": []}); want.add(("invented_commitment", "CX"))
        elif f == "silent":
            k = pick(lambda k: k not in dependents and "CF" + k[1:] not in [x["id"] for x in coms])
            if k:
                scope.remove(k); want.add(("silent_exclusion", k))
                for cm in coms:
                    if k in cm["refs"]:
                        cm["refs"].remove(k)
        elif f == "missing_dep":
            k = pick(lambda k: k in dependents and all(x not in used for x in dependents[k]) and "CF" + k[1:] not in [x["id"] for x in coms])
            if k:
                scope.remove(k); p["proposal"]["exclusions"].append(k)
                for cm in coms:
                    if k in cm["refs"]:
                        cm["refs"].remove(k)
                for x in dependents[k]:
                    want.add(("missing_dependency", x))
        elif f == "early":
            coms[2]["value"] = "2027-01-2%d" % rng.randint(0, 9); want.add(("unsupported_date", "CD"))
    tot = {b: sum((Decimal(R[k]["estimate_hours"][b]) for k in scope), Decimal(0)) for b in ("low", "likely", "high")}
    rate = Decimal("150.00")
    est = p["proposal"]["estimate"]
    if "fixed_ok" in flaws or "fixed_low" in flaws:
        h = tot["high"] + (Decimal(rng.randint(0, 20)) if "fixed_ok" in flaws else -Decimal("0.25"))
        est.update({"type": "fixed", "hours": str(h), "price": str((h * rate).quantize(Decimal("0.01")))})
        if "fixed_low" in flaws:
            want.add(("unsupported_fixed_estimate", "estimate")); want.add(("unsupported_fixed_estimate", "CE"))
        if "open" in flaws and "fixed_low" not in flaws:
            want.add(("unsupported_fixed_estimate", "estimate")); want.add(("unsupported_fixed_estimate", "CE"))
    else:
        est["hours"] = {b: str(v) for b, v in tot.items()}
        est["price"] = {b: str((tot[b] * rate).quantize(Decimal("0.01"))) for b in ("low", "high")}
        if "hours_off" in flaws:
            est["hours"]["likely"] = str(tot["likely"] + Decimal("0.25")); want.add(("estimate_mismatch", "hours.likely"))
        if "price_off" in flaws:
            est["price"]["low"] = str((tot["low"] * rate).quantize(Decimal("0.01")) - Decimal("0.01")); want.add(("estimate_mismatch", "price.low"))
    return p, want


def o10(c, seed):
    rng = random.Random(seed)
    pool = ["untrace", "unknown_trace", "nodemo", "tamper", "vague", "open", "resolved", "noac", "invented", "silent", "missing_dep",
            "early", "hours_off", "price_off"]
    bad = 0; total = 0
    for i in range(12):
        n = rng.randint(120, 200)
        if i < 3:
            fl = [] if i < 2 else ["fixed_ok", "resolved"]
        else:
            fl = rng.sample(pool, rng.randint(1, 5))
            if rng.random() < 0.3:
                fl = [x for x in fl if x not in ("hours_off", "price_off")] + [rng.choice(["fixed_ok", "fixed_low"])]
        d = c.fresh()
        p, want = gen(rng, d, n, fl)
        rc, r = c.check(d, p)
        total += 1
        exp_rc = 1 if want else 0
        if rc != exp_rc or r is None or codes(r) != want:
            bad += 1
            print("    unseen %d (n=%d, flaws %s): rc %s want %s; extra %s missing %s" % (i, n, fl, rc, exp_rc,
                  sorted(codes(r) - want)[:4], sorted(want - codes(r))[:4]))
    return bad == 0, "%d seeded unseen packages (120 to 200 requirements, planted flaws) match exactly" % total


PAIRS = [("available 24/7", "closed outside office hours"), ("open around the clock", "only during business hours"),
         ("usable offline at the front desk", "online only"), ("installed on-premises", "a SaaS service"),
         ("booking with no login", "login required for every booking"), ("card data never stored", "payments kept for 7 years")]


def o11(c, seed):
    """r2 (root G31): contradictory requirements stay unresolved or owner-qualified, never plain commitments."""
    rng = random.Random(seed * 11 + 3); res = {}
    def with_r6(p, r6, inp, r1=None):
        p["inputs"].append({"id": "IN9", "text": inp, "source": "ops email 2026-10-02", "date": "2026-10-02"})
        p["requirements"].append({"id": "R6", "text": r6, "traces": ["IN9"], "depends_on": ["R1"], "capability": "CAP-booking",
                                  "estimate_hours": {"low": "4", "likely": "6", "high": "8"},
                                  "acceptance": [{"id": "AC6", "criterion": "the rule is enforced", "measure": "3 of 3 scripted attempts"}]})
        if r1:
            req(p, "R1")["text"] = r1
        p["proposal"]["scope"].append("R6"); est = p["proposal"]["estimate"]; rate = Decimal(p["rate"]["per_hour"])
        for t, n in (("low", 4), ("likely", 6), ("high", 8)):
            est["hours"][t] = str(Decimal(est["hours"][t]) + n)
        est["price"] = {b: str((Decimal(est["hours"][b]) * rate).quantize(Decimal("0.01"))) for b in ("low", "high")}
        for cm in p["proposal"]["commitments"][:2]:
            cm["refs"].append("R6")
    a_, b_ = rng.choice(PAIRS)
    p = base(); with_r6(p, "Booking " + b_, "Front desk asked for booking " + b_, "Online booking of appointments " + a_)
    rc, r = c.check(c.fresh(), p)
    res["req_vs_req"] = rc == 1 and ("unresolved_conflict", "R1") in codes(r) and ("unresolved_conflict", "R6") in codes(r) and ("commitment_on_blocked_requirement", "C1") in codes(r)
    a_, b_ = rng.choice(PAIRS)
    p = base(); with_r6(p, "Patients can book " + a_, "Owner wants booking " + b_)
    rc, r = c.check(c.fresh(), p)
    res["req_vs_its_input"] = rc == 1 and ("unresolved_conflict", "R6") in codes(r)
    a_, b_ = rng.choice(PAIRS)
    p = base(); with_r6(p, "Booking " + b_, "Booking " + b_)
    p["proposal"]["commitments"].append({"id": "C9", "kind": "sla", "text": "Booking " + a_, "refs": ["R1"]})
    rc, r = c.check(c.fresh(), p)
    res["commitment_text"] = rc == 1 and ("conflicting_commitment", "C9") in codes(r)
    p = base(); with_r6(p, "Front desk can block days for staff training", "Front desk wants to block days"); req(p, "R6")["conflicts_with"] = ["R3"]
    rc, r = c.check(c.fresh(), p)
    res["declared"] = rc == 1 and ("unresolved_conflict", "R3") in codes(r) and ("unresolved_conflict", "R6") in codes(r)
    a_, b_ = rng.choice(PAIRS)
    for st in ("open", "resolved"):
        p = base(); with_r6(p, "Booking " + b_, "Booking " + b_, "Online booking of appointments " + a_)
        amb = {"id": "AMB9", "about": ["R1", "R6"], "question": "which governs?", "escalated_to": "Clinic owner", "status": st}
        if st == "resolved":
            amb["resolution"] = {"text": "R6 governs", "source": "owner email 2026-10-03", "date": "2026-10-03"}
        p["ambiguities"] = (p.get("ambiguities") or []) + [amb]
        rc, r = c.check(c.fresh(), p)
        if st == "open":
            res["open_blocks_with_owner"] = rc == 1 and ("open_ambiguity", "R6") in codes(r) and any(x["id"] == "AMB9" and x["escalated_to"] == "Clinic owner" for x in (r or {}).get("escalations", []))
        else:
            m = {x["commitment"]: x for x in r["trace_matrix"]} if r else {}
            res["resolved_is_qualified"] = rc == 0 and m.get("C1", {}).get("qualified_by") == ["AMB9"] and m.get("C4", {}).get("qualified_by") == [] \
                and any(x["status"] == "resolved" and x["owner"] == ["Clinic owner"] for x in (r or {}).get("conflicts", [])) and "not_checked" in (r or {}).get("coherence", {})
    p = base(); req(p, "R1")["text"] = "Online booking, moving and cancelling of appointments, onboarding call included"
    rc, r = c.check(c.fresh(), p)
    res["no_false_hit"] = rc == 0 and (r or {}).get("conflicts") == []
    bad = sorted(k for k, v in res.items() if not v)
    return not bad, "contradictions block until an owner resolves them (req vs req, req vs input, commitment text, declared, open with owner); resolved ones qualify commitments; no false hit" if not bad else "failed %s" % bad


def s1(c):
    before = {p: sha(p) for p in FIX.rglob("*") if p.is_file()}
    src = Path(c.tool).read_text() if Path(c.tool).is_file() else ""
    banned = [w for w in ("import socket", "import subprocess", "urllib", "http.client", "smtplib", "os.system") if w in src]
    return (not banned and Path(c.tool).is_file(), "no network, mail or process use in the tool%s" % (": " + ", ".join(banned) if banned else "")), before


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tool", default=str(TOOL)); ap.add_argument("--seed", type=int, default=31)
    a = ap.parse_args()
    c = Ctx(a.tool)
    (s1ok, s1msg), before = s1(c)
    checks = [o1, o2, o3, o4, o5, o6, o7, o8, o9, lambda c: o10(c, a.seed), lambda c: o11(c, a.seed)]
    names = ["o1", "o2", "o3", "o4", "o5", "o6", "o7", "o8", "o9", "o10", "o11"]
    passed = 0
    for nm, fn in zip(names, checks):
        try:
            ok, msg = fn(c)
        except Exception as ex:  # a broken tool must fail the check, not the oracle
            ok, msg = False, "error %s: %s" % (type(ex).__name__, ex)
        passed += bool(ok); print("%s %s %s" % ("PASS" if ok else "FAIL", nm, msg))
    after = {p: sha(p) for p in FIX.rglob("*") if p.is_file()}
    ok = s1ok and after == before
    passed += ok; print("%s s1 %s; fixtures byte-identical" % ("PASS" if ok else "FAIL", s1msg))
    shutil.rmtree(str(c.tmp), ignore_errors=True)
    n = len(names) + 1
    print("%s %d/%d" % ("ACCEPTED" if passed == n else "REJECTED", passed, n))
    return 0 if passed == n else 1


if __name__ == "__main__":
    sys.exit(main())
