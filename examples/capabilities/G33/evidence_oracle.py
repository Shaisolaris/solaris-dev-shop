#!/usr/bin/env python3
"""G33 oracle: evidence-backed product decision against the fixture, failure cases and seeded packages.
Usage: evidence_oracle.py [--tool PATH] [--seed N]. Prints ACCEPTED n/n or REJECTED k/n."""
import argparse, copy, hashlib, json, os, random, shutil, subprocess, sys, tempfile
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TOOL = ROOT / "employees" / "product-project" / "product-manager" / "evidence_decision.py"
FIX = HERE / "fixtures"
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def base():
    return json.loads((FIX / "choice.json").read_text())


class Ctx:
    def __init__(self, tool):
        self.tool = tool
        self.tmp = Path(tempfile.mkdtemp(prefix="g33-oracle-"))
        self.n = 0

    def fresh(self):
        self.n += 1
        d = self.tmp / ("w%d" % self.n)
        shutil.copytree(str(FIX), str(d))
        return d

    def run(self, d, pkg=None):
        if not Path(self.tool).is_file():
            return 127, None
        p = d / "pkg.json"
        p.write_text(json.dumps(pkg or json.loads((d / "choice.json").read_text())))
        r = subprocess.run([sys.executable, str(self.tool), "decide", str(p), "--json"], capture_output=True, text=True, env=ENV, timeout=300)
        try:
            return r.returncode, json.loads(r.stdout)
        except ValueError:
            return r.returncode, None


def codes(r):
    return set() if not r else {(f["code"], f["ref"]) for f in r.get("findings", [])}


def o1(c):
    rc, r = c.run(c.fresh())
    ok = (rc == 0 and r and r["status"] == "preferred" and r["preferred"] == "portal"
          and r["totals"]["portal"] == {"high": "3.9500", "low": "3.5000", "point": "3.8214", "unknown_dimensions": []}
          and r["totals"]["ai-schedule"]["point"] == "0.9500"
          and {x["claim"] for x in r["excluded"]} == {"C9", "C10"}
          and len(r["verify_before_use"]) == 1 and r["verify_before_use"][0]["source"] == "S-mkt"
          and r["estimates_made"].startswith("none"))
    return ok, "clean fixture prefers portal; out-of-ICP and stale market claim excluded; no invented TAM"


def o2(c):
    d = c.fresh(); (d / "sources" / "ana.txt").write_text("edited"); rc1, r1 = c.run(d)
    p = base(); [x for x in p["claims"] if x["id"] == "C1"][0]["quote"] = "made-up quote"; rc2, r2 = c.run(c.fresh(), p)
    p = base(); [x for x in p["claims"] if x["id"] == "C6"][0]["value"] = "99%"; rc3, r3 = c.run(c.fresh(), p)
    p = base(); [x for x in p["claims"] if x["id"] == "C8"][0]["value"] = "99"; rc4, r4 = c.run(c.fresh(), p)
    p = base(); [x for x in p["claims"] if x["id"] == "C8"][0]["score"] = "5"; rc5, r5 = c.run(c.fresh(), p)
    ok = (rc1 == 1 and ("snapshot_mismatch", "C1") in codes(r1) and rc2 == 1 and ("quote_not_in_source", "C1") in codes(r2)
          and rc3 == 1 and ("value_not_in_quote", "C6") in codes(r3) and rc4 == 1 and ("g13_value_mismatch", "C8") in codes(r4)
          and rc5 == 1 and ("stated_score_mismatch", "C8") in codes(r5))
    return ok, "changed snapshot, invented quote, value not in quote, G13 mismatch and stated score mismatch all block"


def o3(c):
    p = base()
    for cid, sc in (("C1", "1"), ("C5", "1"), ("C6", "1"), ("C11", "5"), ("C4", "4")):
        [x for x in p["claims"] if x["id"] == cid][0]["score"] = sc
    rc1, r1 = c.run(c.fresh(), p)
    p2 = base()
    for cid, sc in (("C1", "1"), ("C5", "2"), ("C6", "1")):
        [x for x in p2["claims"] if x["id"] == cid][0]["score"] = sc
    rc2, r2 = c.run(c.fresh(), p2)
    ok = (rc1 == 0 and r1["preferred"] == "ai-schedule" and r1["totals"]["ai-schedule"]["low"] == "3.9500"
          and rc2 == 1 and r2["status"] == "no_robust_choice" and r2["preferred"] is None
          and r2["totals"]["portal"]["low"] == "2.1500" and r2["totals"]["reports"]["high"] == "2.3000"
          and r2["deciding_evidence"][0] == {"option": "reports", "dimension": "proof", "weighted_range": "1.2500", "why": "no evidence"})
    return ok, "preference flips when scores change; overlapping ranges give no robust choice with deciding cells"


def o4(c):
    p = base(); p["claims"].append({"id": "C99", "option": "portal", "dimension": "pain", "source": "S-ana", "segment": "mid-size clinics",
                                    "confidence": "high", "score": "0", "quote": "Double bookings happen twice a week."})
    rc, r = c.run(c.fresh(), p)
    cell = [x for x in r["cells"] if x["option"] == "portal" and x["dimension"] == "pain"][0] if r else {}
    ok = (rc == 1 and r["status"] == "no_robust_choice" and [x["claim"] for x in r["contrary_evidence"]] == ["C99"]
          and cell.get("conflict") is True and cell.get("mean") == "3.3000" and r["totals"]["portal"]["low"] == "1.7000")
    return ok, "a contrary claim is listed, marks the cell as conflicting and removes the robust preference"


def o5(c):
    p = base(); p["sources"] = [s for s in p["sources"] if s["id"] != "S-g13"]; p["claims"] = [x for x in p["claims"] if x["source"] != "S-g13"]
    rc1, r1 = c.run(c.fresh(), p)
    p = base(); p["claims"] = [x for x in p["claims"] if x["id"] != "C10"]
    [s for s in p["sources"] if s["id"] == "S-mkt"][0]["retrieved_at"] = "2026-09-20"
    p["claims"].append({"id": "C10b", "option": "reports", "dimension": "proof", "source": "S-mkt", "segment": "mid-size clinics", "confidence": "low",
                        "value": "18,000", "quote": "Headline figure: addressable clinics in North America: 18,000."})
    rc2, r2 = c.run(c.fresh(), p)
    p = base(); p["tam"] = "18000"; rc3, _ = c.run(c.fresh(), p)
    p = base(); [x for x in p["sources"] if x["id"] == "S-g13"][0]["contract"] = "g13-gaps/contract.json"
    for x in p["claims"]:
        if x["source"] == "S-g13":
            x["value"] = "8"
    rc4, r4 = c.run(c.fresh(), p)
    ok = (rc1 == 0 and r1["totals"]["portal"]["unknown_dimensions"] == ["proof"] and r1["totals"]["portal"]["high"] == "4.7000"
          and rc2 == 0 and not r2["verify_before_use"] and r2["totals"]["reports"]["low"] == "2.3000" and rc3 == 2
          and rc4 == 0 and r4["claim_confidence"]["C8"] == "low" and r4["claim_confidence"]["C1"] == "high")
    return ok, "unknown dimension spans 0 to 5; a fresh mutable source is used on its metric scale; G13 with gaps counts as low confidence; top-level TAM refused"


def o6(c):
    bad = []
    p = base(); p["schema"] = "x"; bad.append(p)
    p = base(); p["dimensions"][0]["weight"] = "0.5"; bad.append(p)
    p = base(); p["claims"][0]["score"] = "6"; bad.append(p)
    p = base(); p["claims"][0]["option"] = "nope"; bad.append(p)
    p = base(); p["sources"][0]["snapshot"]["path"] = "../outside.txt"; bad.append(p)
    p = base(); p["decision"]["as_of"] = "2026-09-01"; bad.append(p)  # source retrieved after as_of
    p = base(); p["dimensions"][2]["metric_scale"]["thresholds"] = ["1", "1", "2", "3", "4"]; bad.append(p)
    ok = True
    for p in bad:
        d = c.fresh(); before = sorted(x.name for x in d.rglob("*"))
        q = d / "pkg.json"; q.write_text(json.dumps(p)); o = d / "out.json"
        r = subprocess.run([sys.executable, str(c.tool), "decide", str(q), "--out", str(o)], capture_output=True, text=True, env=ENV)
        ok = ok and r.returncode == 2 and not o.exists()
    return ok, "%d invalid packages refused, nothing written" % len(bad)


def o7(c):
    d = c.fresh(); p = d / "choice.json"; o = d / "res.json"
    r1 = subprocess.run([sys.executable, str(c.tool), "decide", str(p), "--out", str(o)], capture_output=True, text=True, env=ENV)
    r2 = subprocess.run([sys.executable, str(c.tool), "verify", str(o), str(p)], capture_output=True, text=True, env=ENV)
    j = json.loads(o.read_text()); j["preferred"] = "reports"; t = d / "t.json"; t.write_text(json.dumps(j))
    r3 = subprocess.run([sys.executable, str(c.tool), "verify", str(t), str(p)], capture_output=True, text=True, env=ENV)
    keep = o.read_bytes(); bad = d / "bad.json"; bad.write_text("{")
    r4 = subprocess.run([sys.executable, str(c.tool), "decide", str(bad), "--out", str(o)], capture_output=True, text=True, env=ENV)
    r5 = subprocess.run([sys.executable, str(c.tool), "decide", str(p), "--out", str(p)], capture_output=True, text=True, env=ENV)
    ok = (r1.returncode == 0 and r2.returncode == 0 and "IDENTICAL" in r2.stdout and r3.returncode == 1 and "DIFFERENT" in r3.stdout
          and r4.returncode == 2 and o.read_bytes() == keep and r5.returncode == 2)
    return ok, "--out and verify; tampered result detected; failed run keeps earlier result; input overwrite refused"


W = {"low": 1, "medium": 2, "high": 3}


def ref_totals(opts, dims, claims):
    """Independent reference: per option, low/high/point totals and the robust preference."""
    out = {}
    for o in opts:
        lo = hi = pt = Decimal(0); unknown = False
        for dk, w in dims:
            ev = [x for x in claims if x["option"] == o and x["dimension"] == dk]
            if not ev:
                unknown = True; hi += w * 5; continue
            sc = [Decimal(x["score"]) for x in ev]
            lo += w * min(sc); hi += w * max(sc)
            pt += w * sum(W[x["confidence"]] * Decimal(x["score"]) for x in ev) / sum(W[x["confidence"]] for x in ev)
        out[o] = (lo, hi, None if unknown else pt)
    pref = [o for o in opts if all(out[o][0] > out[x][1] for x in opts if x != o)]
    return out, (pref[0] if pref else None)


def o8(c, seed):
    rng = random.Random(seed); ok = True; total = 0; robust = 0
    text = "Generated transcript line for the seeded oracle packages.\n"
    for i in range(40):
        d = c.fresh(); f = d / "sources" / "gen.txt"; f.write_text(text); h = sha(f)
        n = rng.randint(2, 6)
        opts = ["O%d" % k for k in range(n)]
        ws = [rng.randint(1, 8) for _ in range(rng.randint(2, 5))]
        tot = sum(ws); wd = [Decimal(x) / tot for x in ws]
        wd = [w.quantize(Decimal("0.0001")) for w in wd]; wd[-1] = Decimal(1) - sum(wd[:-1])
        dims = [("D%d" % k, w) for k, w in enumerate(wd)]
        strong = rng.choice(opts) if rng.random() < 0.5 else None
        claims = []
        for o in opts:
            for dk, _ in dims:
                if rng.random() < 0.15:
                    continue
                for j in range(rng.randint(1, 3)):
                    sc = Decimal(rng.randint(8, 10) if o == strong else rng.randint(0, 6)) / 2
                    claims.append({"id": "C%s%s%d" % (o, dk, j), "option": o, "dimension": dk, "source": "S0", "segment": "mid-size clinics",
                                   "confidence": rng.choice(["low", "medium", "high"]), "score": str(sc),
                                   "quote": "Generated transcript line for the seeded oracle packages."})
        if rng.random() < 0.3:  # out-of-ICP noise must not count
            claims.append({"id": "Cnoise%d" % i, "option": opts[0], "dimension": dims[0][0], "source": "S0", "segment": "enterprise",
                           "confidence": "high", "score": "5", "quote": "Generated transcript line for the seeded oracle packages."})
        p = {"schema": "solaris.evidence-decision/1",
             "decision": {"question": "q", "owner": "o", "as_of": "2026-10-06", "icp": {"segment": "mid-size clinics", "definition": "d"}},
             "options": [{"id": o, "label": o} for o in opts], "dimensions": [{"id": dk, "label": dk, "weight": str(w)} for dk, w in dims],
             "sources": [{"id": "S0", "kind": "interview", "title": "t", "retrieved_at": "2026-09-01", "snapshot": {"path": "sources/gen.txt", "sha256": h}}],
             "claims": claims}
        want, pref = ref_totals(opts, dims, [x for x in claims if x["segment"] == "mid-size clinics"])
        rc, r = c.run(d, p); total += 1; robust += pref is not None
        good = r is not None and rc == (0 if pref else 1) and r["preferred"] == pref
        for o in opts:
            lo, hi, pt = want[o]
            q = lambda v: str(v.quantize(Decimal("0.0001")))
            good = good and r["totals"][o]["low"] == q(lo) and r["totals"][o]["high"] == q(hi) and r["totals"][o]["point"] == (None if pt is None else q(pt))
        if not good:
            ok = False; print("    unseen %d: rc %s pref %s want %s" % (i, rc, r and r.get("preferred"), pref))
    return ok, "%d seeded packages (%d with a robust winner) match an independent reference on totals and choice" % (total, robust)


def o9(c):
    """r2: no adoption figure enters the package, and a quantity dimension is scored only from a stated number."""
    ok = True
    for key, val in (("adoption", "35%"), ("adoption_rate", "0.2"), ("assumed_adoption", 0.35), ("tam", "1")):
        p = base(); p[key] = val; d = c.fresh(); q = d / "pkg.json"; q.write_text(json.dumps(p)); o = d / "out.json"
        r = subprocess.run([sys.executable, str(c.tool), "decide", str(q), "--out", str(o)], capture_output=True, text=True, env=ENV)
        ok = ok and r.returncode == 2 and not o.exists()
    p = base(); p["dimensions"][0]["quantity"] = True  # pain: C1 has a number but no value; C2, C5, C11 state no number
    for cl in p["claims"]:
        if cl["id"] == "C7":
            cl["value"] = "board reports"  # appears in its quote but is not a number
    rc, r = c.run(c.fresh(), p)
    want = {("value_not_in_quote", k) for k in ("C1", "C2", "C5", "C7", "C11")}
    ok = ok and rc == 1 and r is not None and codes(r) == want and r.get("preferred") is None
    p = base(); p["dimensions"][0]["quantity"] = True
    p["claims"] = [x for x in p["claims"] if x["id"] not in ("C2", "C5", "C11")]
    for cl in p["claims"]:
        if cl["id"] == "C1":
            cl["value"] = "40"
    rc, r = c.run(c.fresh(), p)
    ok = ok and rc == 0 and r is not None and not codes(r) and r.get("preferred") == "portal"
    return ok, "top-level adoption, adoption_rate, assumed_adoption and tam refused; a quantity dimension uses only claims with a numeric value in the quote"


def o10(c):
    """r3 (root G33): a numeric value must be a whole number in the quote; 4 never matches 40, 18 never matches 18,000."""
    ok = True
    for quote, val, flag in (("I would pay about 40 dollars per provider per month for that alone.", "4", True),
                             ("We run 18,000 visits a month across the clinics.", "18", True),
                             ("We run 18,000 visits a month across the clinics.", "180", True),
                             ("We moved 12 points on retention.", "12%", True),
                             ("We run 18,000 visits a month across the clinics.", "18,000", False),
                             ("We run 18,000 visits a month across the clinics.", "18000", False),
                             ("I would pay about 40 dollars per provider per month for that alone.", "40", False)):
        p = base(); p["dimensions"][0]["quantity"] = True
        p["claims"] = [x for x in p["claims"] if x["id"] not in ("C2", "C5", "C11")]
        for cl in p["claims"]:
            if cl["id"] == "C1":
                cl["quote"] = quote; cl["value"] = val
        d = c.fresh(); snap = d / "sources" / "ana.txt"
        if quote not in snap.read_text():
            snap.write_text(snap.read_text() + "\n" + quote + "\n")
            for sr in p["sources"]:
                if sr["id"] == "S-ana":
                    sr["snapshot"]["sha256"] = sha(snap)
        rc, r = c.run(d, p)
        hit = r is not None and ("value_not_in_quote", "C1") in codes(r)
        ok = ok and r is not None and hit == flag and rc == (1 if flag else 0)
    return ok, "numeric values match whole numbers only: 4 vs 40, 18 and 180 vs 18,000, 12% vs 12 points flagged; 40, 18,000 and 18000 accepted"


def s1(c):
    src = Path(c.tool).read_text() if Path(c.tool).is_file() else ""
    banned = [w for w in ("urllib", "http.client", "import socket", "smtplib", "import subprocess", "os.system") if w in src]
    return bool(src) and not banned, "no network, mail or process use in the tool%s" % (": " + ", ".join(banned) if banned else "")


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tool", default=str(TOOL)); ap.add_argument("--seed", type=int, default=33)
    a = ap.parse_args(); c = Ctx(a.tool)
    before = {p: p.read_bytes() for p in FIX.rglob("*") if p.is_file()}
    checks = [("o1", o1), ("o2", o2), ("o3", o3), ("o4", o4), ("o5", o5), ("o6", o6), ("o7", o7), ("o8", lambda c: o8(c, a.seed)), ("o9", o9), ("o10", o10), ("s1", s1)]
    passed = 0
    for nm, fn in checks:
        try:
            ok, msg = fn(c)
        except Exception as ex:
            ok, msg = False, "error %s: %s" % (type(ex).__name__, ex)
        if nm == "s1":
            ok = ok and before == {p: p.read_bytes() for p in FIX.rglob("*") if p.is_file()}; msg += "; fixtures byte-identical"
        passed += bool(ok); print("%s %s %s" % ("PASS" if ok else "FAIL", nm, msg))
    shutil.rmtree(str(c.tmp), ignore_errors=True)
    print("%s %d/%d" % ("ACCEPTED" if passed == len(checks) else "REJECTED", passed, len(checks)))
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
