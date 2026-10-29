#!/usr/bin/env python3
"""G17 oracle: does a resource/cash decision checker reject impossible plans, keep assumptions explicit,
rerun its arithmetic and avoid invented certainty?

Runs CHECKER as `python CHECKER evaluate PACKAGE --json` (and `verify`) on synthetic packages in a temporary
directory. Seeded unseen packages are compared with an independent reference schedule and cash model below.
Usage: decision_oracle.py [--tool CHECKER] [--json] [--seed N]
"""
import argparse
import copy
import hashlib
import json
import math
import os
from fractions import Fraction
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_TOOL = ROOT / "employees/leadership/coo/resource_decision.py"
FIX = HERE / "fixtures"
STUDIO = json.loads((FIX / "studio.json").read_text())
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")
FORBIDDEN = ("guarantee", "will succeed", "certain to", "we recommend", "recommended option", "definitely")


def digest(d):
    h = hashlib.sha256()
    for root, dirs, files in os.walk(str(d)):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(p.encode()); h.update(open(p, "rb").read())
    return h.hexdigest()


class Runner(object):
    def __init__(self, tool, tmp):
        self.tool, self.tmp, self.n, self.unchanged = str(Path(tool).resolve()), Path(tmp), 0, True

    def case(self, pkg, books=True):
        self.n += 1
        d = self.tmp / ("c%03d" % self.n)
        d.mkdir()
        if books:
            for b in ("books-sept", "books-unreconciled"):
                shutil.copytree(str(FIX / b), str(d / b))
        (d / "pkg.json").write_text(json.dumps(pkg, indent=1))
        return d

    def run(self, d, *args):
        before = digest(d)
        p = subprocess.run([sys.executable, self.tool] + list(args), capture_output=True, text=True, env=ENV,
                           timeout=300, cwd=str(d))
        after = digest(d)
        if before != after and "--out" not in args:
            self.unchanged = False
        return p.returncode, p.stdout, p.stderr

    def evaluate(self, pkg, books=True):
        d = self.case(pkg, books)
        rc, out, err = self.run(d, "evaluate", "pkg.json", "--json")
        try:
            js = json.loads(out)
        except ValueError:
            js = None
        return rc, js, out + err, d


def opt(js, oid):
    for o in (js or {}).get("options") or []:
        if o.get("id") == oid:
            return o
    return {}


def down(js, oid):
    return (opt(js, oid).get("cases") or {}).get("downside") or {}


def variant(fn):
    p = copy.deepcopy(STUDIO)
    fn(p)
    return p


# ------------------------------------------------------------------ independent reference model
ADV = {"hours": "high", "people": "low", "hours_per_week": "low", "focus": "low", "from_week": "high",
       "ramp_weeks": "high", "until_week": "low", "opening": "low", "monthly_inflow": "low",
       "monthly_outflow": "high", "monthly_cost": "high", "one_time_cost": "high", "cost_from_week": "low",
       "cost_until_week": "high", "min_buffer_months": "high"}


def ref_model(p):
    A = p["assumptions"]

    def v(name, field, case):
        a = A[name]
        x = Fraction(str(a["value"]))
        if case == "downside":
            side = a.get("downside") or ADV[field]
            x = Fraction(str(a.get(side, a["value"])))
        return x
    res = {}
    H = p["calendar"]["weeks"]
    for o in p["options"]:
        res[o["id"]] = {}
        for case in ("base", "downside"):
            caps = {}
            for c in p["capacity"]:
                caps[c["role"]] = (v(c["people"], "people", case), v(c["hours_per_week"], "hours_per_week", case),
                                   v(c["focus"], "focus", case))
            items = [w for w in p["work"] if w["id"] not in o.get("descope", [])]
            rem = {w["id"]: v(w["hours"], "hours", case) for w in items}
            done = {}
            for week in range(1, H + 1):
                for role, (pp, hh, ff) in sorted(caps.items()):
                    cap = pp * hh * ff
                    for a in o.get("capacity_add", []):
                        if a["role"] != role:
                            continue
                        s = v(a["from_week"], "from_week", case)
                        u = v(a["until_week"], "until_week", case) if "until_week" in a else None
                        if week >= s and (u is None or week <= u):
                            full = v(a["people"], "people", case) * hh * ff
                            cap += full / 2 if week < s + v(a["ramp_weeks"], "ramp_weeks", case) else full
                    ready = sorted([w for w in items if w["role"] == role and w["id"] not in done and
                                    all(x in done and done[x] < week for x in w.get("after", []))],
                                   key=lambda w: (w.get("priority", 1), w["id"]))
                    for w in ready:
                        if cap <= 0:
                            break
                        lim = rem[w["id"]] if w.get("max_people") is None else min(rem[w["id"]], w["max_people"] * hh * ff)
                        t = min(cap, lim)
                        rem[w["id"]] -= t
                        cap -= t
                        if rem[w["id"]] <= 0:
                            done[w["id"]] = week
            c = p["cash"]
            bal = v(c["opening"], "opening", case)
            inflow, outflow = v(c["monthly_inflow"], "monthly_inflow", case), v(c["monthly_outflow"], "monthly_outflow", case)
            buf_m = v(c["min_buffer_months"], "min_buffer_months", case)
            k = Fraction(12, 52)
            cf = max(1, math.ceil(v(o["cost_from_week"], "cost_from_week", case))) if "cost_from_week" in o else 1
            cu = math.floor(v(o["cost_until_week"], "cost_until_week", case)) if "cost_until_week" in o else H
            low, breach = bal, None
            for week in range(1, H + 1):
                mc = v(o["monthly_cost"], "monthly_cost", case) if "monthly_cost" in o and cf <= week <= cu else 0
                out = (outflow + mc) * k
                if "one_time_cost" in o and week == cf:
                    out += v(o["one_time_cost"], "one_time_cost", case)
                bal += inflow * k - out
                low = min(low, bal)
                if breach is None and bal < buf_m * (outflow + mc):
                    breach = week
            res[o["id"]][case] = {"finish": {w["id"]: done.get(w["id"]) for w in items}, "lowest": low, "breach": breach}
    return res


def cents(x):
    from decimal import Decimal, ROUND_HALF_EVEN
    return str((Decimal(x.numerator) / Decimal(x.denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))


def gen(rng):
    A = {}

    def a(name, value, low=None, high=None, **kw):
        d = {"value": value, "source": "seeded synthetic", "dated": "2026-10-01"}
        if low is not None:
            d["low"] = low
        if high is not None:
            d["high"] = high
        d.update(kw)
        A[name] = d
        return name
    roles = ["r%d" % i for i in range(rng.randint(1, 3))]
    cap = [{"role": r, "people": a("p_" + r, rng.randint(1, 5), exact=True), "hours_per_week": a("h_" + r, 40, low=rng.choice([32, 36, 40])),
            "focus": a("f_" + r, "0.7", low=rng.choice(["0.5", "0.6", "0.7"]))} for r in roles]
    work = []
    for i in range(rng.randint(3, 8)):
        w = {"id": "w%d" % i, "role": rng.choice(roles), "hours": a("e%d" % i, rng.randint(20, 400), high=rng.randint(400, 500)),
             "priority": rng.randint(1, 3)}
        prev = ["w%d" % j for j in range(i) if rng.random() < 0.3]
        if prev:
            w["after"] = prev
        if rng.random() < 0.3:
            w["max_people"] = rng.randint(1, 3)
        work.append(w)
    opts = [{"id": "base", "reversible": True, "undo": {"weeks": a("z", 0, exact=True), "cost": "z"}}]
    r = rng.choice(roles)
    opts.append({"id": "add", "reversible": True, "undo": {"weeks": "z", "cost": "z"},
                 "capacity_add": [{"role": r, "people": a("ap", rng.randint(1, 3), exact=True), "from_week": a("af", rng.randint(1, 6), high=rng.randint(6, 9)),
                                   "ramp_weeks": a("ar", rng.randint(0, 3), high=rng.randint(3, 4)), "until_week": a("au", rng.randint(10, 20), low=rng.randint(8, 10))}],
                 "monthly_cost": a("am", rng.randint(5000, 40000), high=45000), "cost_from_week": a("acf", rng.randint(1, 6), low=1),
                 "cost_until_week": a("acu", rng.randint(10, 20), high=rng.randint(20, 24)), "one_time_cost": a("ao", rng.randint(0, 20000), exact=True)})
    if len(work) > 3:
        leaf = [w["id"] for w in work if not any(w["id"] in x.get("after", []) for x in work)]
        opts.append({"id": "cut", "reversible": False, "why_irreversible": "seeded", "descope": [leaf[0]]})
    needs = [work[-1]["id"]]
    if any(needs[0] in o.get("descope", []) for o in opts):
        needs = [work[0]["id"]]
        for o in opts:
            if needs[0] in o.get("descope", []):
                o["descope"] = []
    return {"schema": "solaris.resource-decision/1",
            "decision": {"question": "seeded synthetic decision", "owner": "seeded owner", "as_of": "2026-10-05", "currency": "USD"},
            "assumptions": A, "calendar": {"start": "2026-10-05", "weeks": rng.randint(12, 30)}, "capacity": cap, "work": work,
            "milestones": [{"id": "m", "needs": needs, "deadline_week": rng.randint(4, 20)}],
            "cash": {"opening": a("co", rng.randint(100000, 600000), low=rng.randint(50000, 100000)), "monthly_inflow": a("ci", rng.randint(50000, 150000), low=40000),
                     "monthly_outflow": a("cb", rng.randint(60000, 150000), high=160000), "min_buffer_months": a("cbuf", rng.choice([1, 2, 3]), exact=True)},
            "options": opts}


# ------------------------------------------------------------------ checks
def run_checks(tool, seed):
    tmp = tempfile.mkdtemp(prefix="g17-oracle-")
    R = Runner(tool, tmp)
    out = []

    def chk(cid, desc, ok, detail=""):
        out.append({"id": cid, "desc": desc, "ok": bool(ok), "detail": str(detail)[:500]})
    try:
        # d1 clean control with hand-checked figures
        rc, js, txt, _ = R.evaluate(STUDIO)
        a = down(js, "as-is")
        ok = rc == 0 and (js or {}).get("status") == "feasible_options" and js.get("feasible_in_downside") == ["descope-reporting"] \
            and a.get("cash", {}).get("lowest") == "337000.00" and "backend short 73.2 hours by week 16" in str(a.get("milestones")) \
            and "backend short 8.4 hours" in str(down(js, "hire").get("milestones")) \
            and (down(js, "contractors").get("cash") or {}).get("buffer_breach", {}).get("week") == 17 \
            and js.get("decision_owner", "").startswith("COO") and "Delivery lead" in str(js.get("dissent")) \
            and js["assumptions"]["inflow"]["value"] == 109500
        chk("d1", "clean studio package: only descope-reporting survives the downside; hand-checked figures", ok,
            "rc=%s status=%s feasible=%s" % (rc, (js or {}).get("status"), (js or {}).get("feasible_in_downside")))

        # d2 impossible schedule rejected with the binding constraint and narrowed alternatives
        p = variant(lambda p: p["milestones"][0].update(deadline_week=6))
        rc, js, txt, _ = R.evaluate(p)
        ms = down(js, "as-is").get("milestones") or [{}]
        ok = rc == 1 and (js or {}).get("status") == "rejected_as_stated" and not js.get("feasible_in_downside") \
            and "dependencies" in str(ms[0].get("binding")) and all(o.get("narrowed") for o in js["options"]) \
            and opt(js, "as-is")["narrowed"].get("earliest_milestone_weeks", {}).get("launch") == 18
        chk("d2", "deadline week 6: rejected, dependency chain named, earliest weeks given for every option", ok,
            "rc=%s status=%s binding=%s" % (rc, (js or {}).get("status"), ms[0].get("binding")))

        # d3 narrowing by dropping optional work that steals capacity; the proposal reruns as feasible
        def steal(p):
            for w in p["work"]:
                if w["id"] == "reporting":
                    w["priority"] = 0
            p["options"] = [o for o in p["options"] if o["id"] == "as-is"]
            p["milestones"][0]["deadline_week"] = 18
        p = variant(steal)
        rc, js, txt, _ = R.evaluate(p)
        nar = opt(js, "as-is").get("narrowed") or {}
        p2 = copy.deepcopy(p)
        p2["options"][0]["descope"] = nar.get("drop_optional_work") or []
        rc2, js2, _, _ = R.evaluate(p2)
        ok = rc == 1 and nar.get("drop_optional_work") == ["reporting"] and nar.get("feasible_downside") is True and rc2 == 0
        chk("d3", "optional reporting work ahead of the launch path: narrowed by dropping it, and the narrowed plan reruns feasible",
            ok, "rc=%s narrowed=%s rerun rc=%s" % (rc, nar, rc2))

        # d4 assumptions explicit: refused with exit 2 and nothing written
        bad = []
        cases = [("literal effort", lambda p: p["work"][0].update(hours=60)),
                 ("no source", lambda p: p["assumptions"]["api_h"].pop("source")),
                 ("undated", lambda p: p["assumptions"]["burn"].pop("dated")),
                 ("dated after as_of", lambda p: p["assumptions"]["burn"].update(dated="2026-11-01")),
                 ("unknown reference", lambda p: p["cash"].update(opening="cash_typo")),
                 ("no owner", lambda p: p["decision"].update(owner="  ")),
                 ("conflicting downside", lambda p: p["assumptions"]["hire_start"].pop("downside")),
                 ("value outside range", lambda p: p["assumptions"]["api_h"].update(high=700)),
                 ("cycle", lambda p: p["work"][0].update(after=["web"])),
                 ("risk without owner", lambda p: p["risks"][0].pop("owner")),
                 ("reversible without undo", lambda p: p["options"][1].pop("undo")),
                 ("irreversible without why", lambda p: p["options"][2].pop("why_irreversible"))]
        for name, fn in cases:
            d = R.case(variant(fn))
            rc, o, e = R.run(d, "evaluate", "pkg.json", "--out", "r.json")
            if rc != 2 or (d / "r.json").exists():
                bad.append((name, rc))
        chk("d4", "12 invalid packages (literal numbers, unsourced, undated, future-dated, unknown ref, no owner, "
                  "conflicting downside, out-of-range, cycle, unowned risk, undo missing, why missing): exit 2, nothing written",
            not bad, bad)

        # d5 G14 evidence: unreconciled books block the decision; currency never converted
        p = variant(lambda p: p["assumptions"]["inflow"]["from_g14"].update(package="books-unreconciled/package.json"))
        rc, js, txt, _ = R.evaluate(p)
        ok1 = rc == 1 and (js or {}).get("status") == "blocked_evidence" and "inflow" in str(js.get("required_evidence"))
        p = variant(lambda p: p["decision"].update(currency="EUR"))
        rc2, js2, txt2, _ = R.evaluate(p)
        chk("d5", "inflow from unreconciled G14 books: blocked_evidence, exit 1; EUR decision on USD books: exit 2",
            ok1 and rc2 == 2, "rc=%s status=%s | eur rc=%s" % (rc, (js or {}).get("status"), rc2))

        # d6 risk realised in the downside only, and it moves the schedule
        p = variant(lambda p: p.update(risks=[]))
        rc, js0, _, _ = R.evaluate(p)
        rc1, js1, _, _ = R.evaluate(STUDIO)
        f0 = down(js0, "descope-reporting").get("finish_weeks", {}).get("integration")
        f1 = down(js1, "descope-reporting").get("finish_weeks", {}).get("integration")
        b0 = ((opt(js0, "as-is").get("cases") or {}).get("base") or {}).get("finish_weeks")
        b1 = ((opt(js1, "as-is").get("cases") or {}).get("base") or {}).get("finish_weeks")
        exp = (opt(js1, "as-is").get("risk_exposure") or [{}])[0]
        chk("d6", "R1 rework adds 60 downside hours to integration: later downside finish, base unchanged, exposure listed",
            f0 is not None and f1 is not None and f1 > f0 and b0 == b1 and exp.get("owner") and exp.get("mitigation"),
            "downside integration %s -> %s; exposure %s" % (f0, f1, exp))

        # d7 reversibility ordering and irreversible-only status
        def two(p):
            p["milestones"][0]["deadline_week"] = 20
            p["assumptions"]["buffer"]["value"] = 1
        rc, js, _, _ = R.evaluate(variant(two))
        fe = (js or {}).get("feasible_in_downside") or []
        ok1 = rc == 0 and "hire" in fe and fe.index("hire") == len(fe) - 1 and len(fe) >= 3
        p = variant(two)
        p["options"] = [o for o in p["options"] if o["id"] == "hire"]
        rc2, js2, _, _ = R.evaluate(p)
        chk("d7", "reversible feasible options listed before the irreversible hire; hire-only feasibility flagged for sign-off",
            ok1 and rc2 == 0 and (js2 or {}).get("status") == "feasible_irreversible_only",
            "feasible=%s | status=%s %s" % (fe, (js2 or {}).get("status"), (js2 or {}).get("feasible_in_downside")))

        # d8 no invented certainty
        rc, js, txt, d = R.evaluate(STUDIO)
        rc_t, text, _ = R.run(d, "evaluate", "pkg.json")
        low = (txt + text).lower()
        p = variant(lambda p: p["assumptions"]["be_people"].pop("exact"))
        rc3, js3, _, _ = R.evaluate(p)
        ok = not any(w in low for w in FORBIDDEN) and "not a forecast" in str((js or {}).get("certainty")) \
            and "decides" in text and "be_people" in str((js3 or {}).get("required_evidence")) \
            and "be_people" not in str((js or {}).get("required_evidence"))
        chk("d8", "no certainty words, certainty limit stated, owner decides; an unranged non-exact figure is named as missing evidence",
            ok, [w for w in FORBIDDEN if w in low])

        # d9 rerunnable arithmetic: verify identical, tampered differs, --out never overwrites the package
        d = R.case(STUDIO)
        rc1, _, _ = R.run(d, "evaluate", "pkg.json", "--out", "r.json")
        rc2, o2, _ = R.run(d, "verify", "pkg.json", "r.json")
        r = json.loads((d / "r.json").read_text()) if (d / "r.json").exists() else {}
        try:
            for o in r["options"]:
                if o["id"] == "as-is":
                    o["cases"]["downside"]["cash"]["lowest"] = "347000.00"
            (d / "t.json").write_text(json.dumps(r))
        except (KeyError, TypeError):
            pass
        rc3, o3, _ = R.run(d, "verify", "pkg.json", "t.json")
        before = (d / "pkg.json").read_bytes()
        rc4, _, _ = R.run(d, "evaluate", "pkg.json", "--out", "pkg.json")
        ok = rc1 == 0 and rc2 == 0 and rc3 == 1 and "lowest" in o3 and rc4 == 2 and (d / "pkg.json").read_bytes() == before
        chk("d9", "evaluate --out then verify: identical; one tampered cash figure: different, named; --out onto the package refused",
            ok, "rc %s %s %s %s" % (rc1, rc2, rc3, rc4))

        # d10 seeded unseen packages against the independent reference model
        rng = random.Random(seed)
        bad, n = [], 0
        for t in range(15):
            p = gen(rng)
            rc, js, txt, _ = R.evaluate(p, books=False)
            if rc not in (0, 1) or js is None:
                bad.append((t, "rc", rc, txt[-200:]))
                continue
            ref = ref_model(p)
            for o in p["options"]:
                for case in ("base", "downside"):
                    got = (opt(js, o["id"]).get("cases") or {}).get(case) or {}
                    want = ref[o["id"]][case]
                    n += 1
                    gb = (got.get("cash") or {}).get("buffer_breach")
                    if got.get("finish_weeks") != want["finish"] or (got.get("cash") or {}).get("lowest") != cents(want["lowest"]) \
                            or (gb or {}).get("week") != want["breach"]:
                        bad.append((t, o["id"], case, got.get("finish_weeks"), want["finish"], (got.get("cash") or {}).get("lowest"), cents(want["lowest"])))
        chk("d10", "15 seeded unseen packages: finish weeks, lowest cash and buffer-breach week match the reference model (%d option-cases)" % n,
            not bad and n > 0, bad[:2])

        # d11 staffing caps: people beyond max_people do not speed an item
        def capped(p):
            for w in p["work"]:
                if w["id"] == "api":
                    w["max_people"] = 3
        rc, js, _, _ = R.evaluate(variant(capped))
        fa = down(js, "as-is").get("finish_weeks", {}).get("api")
        fc = down(js, "contractors").get("finish_weeks", {}).get("api")
        chk("d11", "api capped at three people (the current team): contractors do not finish it sooner", fa is not None and fa == fc,
            "as-is %s contractors %s" % (fa, fc))

        src = Path(tool).read_text() if Path(tool).is_file() else ""
        forb = [w for w in ("import subprocess", "import socket", "urllib", "http.client", "os.system") if w in src]
        chk("s1", "inputs byte-identical after every run; no process or network use", R.unchanged and not forb and R.n > 0, forb)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", default=str(DEFAULT_TOOL))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--seed", type=int, default=1717)
    a = ap.parse_args()
    if not Path(a.tool).is_file():
        res = [{"id": "d0", "desc": "checker exists", "ok": False, "detail": "no such file: %s" % a.tool}]
    else:
        res = run_checks(a.tool, a.seed)
    n = sum(1 for c in res if c["ok"])
    if a.json:
        print(json.dumps({"checks": res, "passed": n, "total": len(res)}, indent=1))
    else:
        for c in res:
            print("%s %s %s%s" % ("PASS" if c["ok"] else "FAIL", c["id"], c["desc"], "" if c["ok"] else "  [" + c["detail"] + "]"))
        print("%s %d/%d" % ("ACCEPTED" if n == len(res) else "REJECTED", n, len(res)))
    return 0 if n == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
