#!/usr/bin/env python3
"""M33 oracle (Grok self-validation, not independent review). Written from M33.md, G33.md and
evidence-product-decision.md before reading the builder's oracle. It keeps an independent Decimal model of the
doc's scoring (confidence-weighted cell mean with low=1, medium=2, high=3; min/max ranges; unknown cell 0..5;
conflict when range >= 2; totals = weight x cell; preferred only when one low total beats every other high total;
metric scale score = number of thresholds <= value) and drives the real CLI on edited copies of the fixture.
Authoring fix after the first run (kept in results/kept, 7/9), disclosed: E07 switched the G13 source to the
g13-gaps contract but kept value 5, so the claims were blocked as g13_value_mismatch before any confidence downgrade
could show. The gaps contract's orders value (8) was taken from the builder's test, not derived here.
Usage: PY m33_oracle.py SRC OUT.json [--tool PATH]."""
import copy, hashlib, json, os, random, shutil, subprocess, sys, tempfile
from decimal import Decimal as D, ROUND_HALF_UP
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]
TOOL = os.path.join(SRC, "employees/product-project/product-manager/evidence_decision.py")
if "--tool" in sys.argv: TOOL = os.path.abspath(sys.argv[sys.argv.index("--tool") + 1])
FIX = os.path.join(SRC, "examples/capabilities/G33/fixtures"); PY = sys.executable; ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
BASE = json.load(open(os.path.join(FIX, "choice.json"))); ROWS = []
CW = {"low": D(1), "medium": D(2), "high": D(3)}
def q4(x): return x.quantize(D("0.0001"), rounding=ROUND_HALF_UP)

class Pkg:
    def __init__(s, p=None):
        s.top = tempfile.mkdtemp(prefix="m33o-"); s.d = os.path.join(s.top, "f"); shutil.copytree(FIX, s.d); s.p = copy.deepcopy(p or BASE)
    def path(s): return os.path.join(s.d, "choice.json")
    def run(s, *extra):
        json.dump(s.p, open(s.path(), "w"), indent=1)
        r = subprocess.run([PY, TOOL] + [x.replace("@P", s.path()) for x in extra], cwd=s.top, env=ENV, capture_output=True, text=True, timeout=120)
        try: j = json.loads(r.stdout)
        except Exception: j = {}
        return r.returncode, j
    def decide(s): return s.run("decide", "@P", "--json")
    def claim(s, cid): return next(c for c in s.p["claims"] if c["id"] == cid)
    def src(s, sid): return next(x for x in s.p["sources"] if x["id"] == sid)
    def close(s): shutil.rmtree(s.top, ignore_errors=True)

def row(name, ok, det): ROWS.append({"row": name, "pass": bool(ok), "detail": det}); print(("PASS " if ok else "FAIL ") + name + " " + json.dumps(det, default=str)[:450], flush=True)
def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + " crash", False, {"crash": repr(e)})
    return g
def fcodes(j): return sorted({(f.get("code") if isinstance(f, dict) else str(f)) for f in (j.get("findings") or [])})
def cell(j, o, d): return next((c for c in j.get("cells", []) if c.get("option") == o and c.get("dimension") == d), None)
def snap_line(name, k=0):
    t = open(os.path.join(FIX, "sources", name)).read().splitlines(); return t[k]

def model(p, scores):
    """scores: {(option, dim): [(score, confidence)]}; returns totals {opt: (low, high, point|None)} and preferred."""
    W = {d["id"]: D(d["weight"]) for d in p["dimensions"]}; tot = {}
    for o in [x["id"] for x in p["options"]]:
        lo = hi = pt = D(0); unk = False
        for d, w in W.items():
            cs = scores.get((o, d), [])
            if not cs: unk = True; hi += w * 5; continue
            m = sum(CW[c] * s for s, c in cs) / sum(CW[c] for s, c in cs); lo += w * min(s for s, _ in cs); hi += w * max(s for s, _ in cs); pt += w * m
        tot[o] = (lo, hi, None if unk else pt)
    pref = [o for o in tot if all(tot[o][0] > tot[x][1] for x in tot if x != o)]
    return tot, (pref[0] if pref else None)

def tool_totals(j): return {o: (D(v["low"]), D(v["high"]), None if v.get("point") is None else D(v["point"])) for o, v in (j.get("totals") or {}).items()}
def same_totals(mine, got): return set(mine) == set(got) and all(q4(mine[o][0]) == got[o][0] and q4(mine[o][1]) == got[o][1] and ((mine[o][2] is None and got[o][2] is None) or (mine[o][2] is not None and got[o][2] is not None and q4(mine[o][2]) == got[o][2])) for o in mine)

def base_scores(p, used, proof_cells):
    s = {}
    for c in p["claims"]:
        if c["id"] in used and "score" in c and c["source"] != "S-g13": s.setdefault((c["option"], c["dimension"]), []).append((D(c["score"]), c["confidence"]))
    for k, v in proof_cells.items(): s.setdefault(k, []).extend(v)
    return s
G13_CELLS = {("portal", "proof"): [(D(2), "high")], ("ai-schedule", "proof"): [(D(2), "high")]}  # metric scale: value 5 -> 2 thresholds (1, 5) <= 5
CLEAN_USED = {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C11", "C13"}

@safe
def e01():
    k = Pkg(); rc, j = k.decide(); k.close(); tot, pref = model(BASE, base_scores(BASE, CLEAN_USED, G13_CELLS))
    txt = json.dumps(j).lower(); no_tam = not any(('"%s"' % x) in txt for x in ("tam", "sam", "som", "market_size", "adoption"))
    exc = sorted(e.get("claim") for e in j.get("excluded", [])); pc = cell(j, "portal", "pain") or {}
    ok = rc == 0 and j.get("preferred") == pref == "portal" and same_totals(tot, tool_totals(j)) and exc == ["C10", "C9"] and pc.get("mean") == "4.7143" and no_tam and "none" in str(j.get("estimates_made"))
    row("E01 clean control: preferred portal; totals equal an independent Decimal model; C9 (segment) and C10 (stale) excluded; no market size computed", ok, {"rc": rc, "pref": j.get("preferred"), "mine": {o: [str(q4(x)) if x is not None else None for x in v] for o, v in tot.items()}, "got": j.get("totals"), "excluded": exc})

@safe
def e02():
    res = {}
    for key in ("tam", "sam", "som", "market_size", "adoption"):
        k = Pkg(); k.p[key] = "18000 clinics"; out = os.path.join(k.d, "r.json"); rc, _ = k.run("decide", "@P", "--out", out); k.close(); res["top_" + key] = (rc == 2 and not os.path.exists(out), rc)
    k = Pkg(); k.src("S-mkt")["retrieved_at"] = "2026-10-01"; rc, j = k.decide(); k.close()
    res["fresh_market_number_score_checked"] = (rc in (0, 1) and "stated_score_mismatch" in fcodes(j) and "C10" not in sum((c.get("claims", []) for c in j.get("cells", [])), []), {"rc": rc, "codes": fcodes(j)})
    k = Pkg(); k.src("S-mkt")["retrieved_at"] = "2026-10-01"; k.claim("C10")["score"] = "5"; rc, j = k.decide(); k.close()
    res["fresh_market_number_consistent_is_used_not_computed"] = (rc in (0, 1) and "C10" in (cell(j, "portal", "proof") or {}).get("claims", []) and "none" in str(j.get("estimates_made")), {"rc": rc, "proof": cell(j, "portal", "proof")})
    k = Pkg(); k.claim("C6")["value"] = "75%"; rc, j = k.decide(); k.close(); res["value_not_in_quote"] = ("value_not_in_quote" in fcodes(j), fcodes(j))
    k = Pkg(); k.claim("C1")["quote"] = "I would pay 400 dollars per provider per month."; rc, j = k.decide(); k.close(); res["invented_quote"] = ("quote_not_in_source" in fcodes(j) and "C1" not in (cell(j, "portal", "pain") or {}).get("claims", []), fcodes(j))
    k = Pkg(); k.claim("C1")["quote"] = "  if a PORTAL let patients book   and move their own slots, i would pay about 40 dollars per provider per month for that alone. "; rc, j = k.decide(); k.close(); res["quote_whitespace_case_normalized_ok"] = (rc == 0 and "C1" in (cell(j, "portal", "pain") or {}).get("claims", []), fcodes(j))
    row("E02 no invented market numbers: top-level TAM/SAM/SOM/market_size/adoption refused and nothing written; a fresh analyst figure is score-checked, used only as evidence; invented values and quotes blocked", all(v[0] for v in res.values()), res)

@safe
def e03():
    res = {}
    def edit(fn, code=None):
        k = Pkg(); fn(k); rc, j = k.decide(); k.close(); return rc, j
    rc, j = edit(lambda k: open(os.path.join(k.d, "sources/ben.txt"), "a").write("edited")); res["snapshot_edited"] = ("snapshot_mismatch" in fcodes(j) and not any(c in ("C3", "C4", "C11") for c in sum((x.get("claims", []) for x in j.get("cells", [])), [])), fcodes(j))
    rc, j = edit(lambda k: os.remove(os.path.join(k.d, "sources/cy.txt"))); res["snapshot_missing"] = ("snapshot_mismatch" in fcodes(j), fcodes(j))
    rc, j = edit(lambda k: k.claim("C3").__setitem__("source", "S-zed")); res["unknown_source"] = ("unknown_source" in fcodes(j), fcodes(j))
    rc, j = edit(lambda k: k.src("S-ben").__setitem__("retrieved_at", "2026-10-07")); res["retrieved_after_as_of"] = (rc == 2 or "C3" not in (cell(j, "portal", "fit") or {}).get("claims", []), rc)
    rc, j = edit(lambda k: k.claim("C3").pop("score")); res["unscored_claim"] = ("unscored_claim" in fcodes(j), fcodes(j))
    rc, j = edit(lambda k: k.claim("C3").__setitem__("score", 4.0)); res["float_score_invalid"] = (rc == 2, rc)
    rc, j = edit(lambda k: k.claim("C3").__setitem__("score", "6")); res["score_above_5_invalid"] = (rc == 2, rc)
    row("E03 source integrity: edited or missing snapshots, unknown sources, late retrieval, unscored claims and bad scores never feed a cell", all(v[0] for v in res.values()), res)

@safe
def e04():
    k = Pkg(); k.p["claims"].append({"id": "C20", "option": "portal", "dimension": "pain", "source": "S-cy", "segment": "mid-size clinics", "confidence": "high", "score": "1",
                                     "quote": "when I called three references only one was still a customer."})
    rc, j = k.decide(); k.close(); pc = cell(j, "portal", "pain") or {}; used = CLEAN_USED | {"C20"}
    sc = base_scores(BASE, CLEAN_USED, G13_CELLS); sc[("portal", "pain")].append((D(1), "high")); tot, pref = model(BASE, sc)
    contrary = json.dumps(j.get("contrary_evidence")); deciding = json.dumps(j.get("deciding_evidence"))
    ok = rc == 1 and j.get("status") == "no_robust_choice" and pref is None and j.get("preferred") in (None, "") and pc.get("conflict") is True and "C20" in contrary and "portal" in deciding and "pain" in deciding and same_totals(tot, tool_totals(j))
    row("E04 conflicting evidence: a strong contrary interview claim makes the portal pain cell a conflict (1..5), lists it as contrary, and the decision becomes no_robust_choice naming that cell", ok,
        {"rc": rc, "status": j.get("status"), "cell": pc, "contrary": j.get("contrary_evidence"), "deciding": j.get("deciding_evidence"), "mine": {o: [str(q4(x)) if x is not None else None for x in v] for o, v in tot.items()}})

@safe
def e05():
    bad = []
    for s5 in range(0, 6):
        for cf in ("low", "medium", "high"):
            k = Pkg(); k.claim("C1")["score"] = str(s5); k.claim("C1")["confidence"] = cf; rc, j = k.decide(); k.close()
            p = copy.deepcopy(BASE); p["claims"][0]["score"] = str(s5); p["claims"][0]["confidence"] = cf; tot, pref = model(p, base_scores(p, CLEAN_USED, G13_CELLS))
            if not (same_totals(tot, tool_totals(j)) and j.get("preferred") == pref and rc == (0 if pref else 1)): bad.append({"score": s5, "conf": cf, "rc": rc, "pref": j.get("preferred"), "mine_pref": pref})
    row("E05 the decision moves predictably: sweeping C1 over scores 0..5 and every confidence gives the model's totals and preference each time", not bad, {"bad": bad[:4]})

@safe
def e06():
    res = {}
    k = Pkg(); k.p["claims"] = [c for c in k.p["claims"] if not (c["option"] == "portal" and c["dimension"] == "fit")]; rc, j = k.decide(); k.close()
    t = (j.get("totals") or {}).get("portal", {}); res["unknown_dimension"] = (rc == 1 and t.get("point") is None and "fit" in t.get("unknown_dimensions", []) and "portal" in json.dumps(j.get("deciding_evidence")), {"rc": rc, "portal": t})
    for age, used in ((30, True), (31, False)):
        k = Pkg(); from datetime import date, timedelta; k.src("S-mkt")["retrieved_at"] = str(date(2026, 10, 6) - timedelta(days=age)); k.claim("C10")["score"] = "5"; rc, j = k.decide(); k.close()
        inc = "C10" in (cell(j, "portal", "proof") or {}).get("claims", []); res["mutable_age_%d" % age] = (inc == used, {"rc": rc, "used": inc, "verify": j.get("verify_before_use")})
    row("E06 unknown dimension spans 0..5 with no point and blocks a robust win; a mutable source is usable at max_age_days and excluded one day later", all(v[0] for v in res.values()), res)

@safe
def e07():
    res = {}
    k = Pkg(); k.src("S-g13")["contract"] = "g13-gaps/contract.json"; k.claim("C8")["value"] = "8"; k.claim("C12")["value"] = "8"; rc, j = k.decide(); k.close(); res["g13_gaps_low_confidence"] = ((j.get("claim_confidence") or {}).get("C8") == "low", {"rc": rc, "C8": (j.get("claim_confidence") or {}).get("C8"), "codes": fcodes(j)})
    k = Pkg(); k.claim("C8")["value"] = "6"; rc, j = k.decide(); k.close(); res["g13_value_mismatch"] = ("g13_value_mismatch" in fcodes(j), fcodes(j))
    k = Pkg(); k.src("S-g13")["contract"] = "g13/missing.json"; rc, j = k.decide(); k.close(); res["g13_unavailable"] = ("g13_unavailable" in fcodes(j), fcodes(j))
    k = Pkg(); k.claim("C8")["score"] = "3"; rc, j = k.decide(); k.close(); res["stated_score_vs_metric"] = ("stated_score_mismatch" in fcodes(j), fcodes(j))
    row("E07 G13 evidence: gaps lower confidence to low; a wrong value, a missing contract and a stated score against the metric scale are named", all(v[0] for v in res.values()), res)

@safe
def e08():
    k = Pkg(); out = os.path.join(k.d, "r.json"); r1, _ = k.run("decide", "@P", "--out", out); good = open(out).read(); v0, _ = k.run("verify", out, "@P")
    r_over, _ = k.run("decide", "@P", "--out", "@P"); pkg_ok = json.load(open(k.path())) == k.p
    k.p["tam"] = "1"; r_inv, _ = k.run("decide", "@P", "--out", out); kept = open(out).read() == good; k.p.pop("tam")
    j = json.loads(good); j["preferred"] = "reports"; open(out, "w").write(json.dumps(j)); v1, _ = k.run("verify", out, "@P"); open(out, "w").write(good[:len(good) // 3]); v2, _ = k.run("verify", out, "@P"); k.close()
    ok = r1 == 0 and v0 == 0 and r_over == 2 and pkg_ok and r_inv == 2 and kept and v1 == 1 and v2 in (1, 2)
    row("E08 recovery: --out refuses the package, an invalid run keeps the earlier result, verify names an edited or truncated result", ok, {"out": r1, "verify": v0, "over_pkg": r_over, "pkg_unchanged": pkg_ok, "invalid": r_inv, "kept": kept, "edited": v1, "truncated": v2})

@safe
def e09():
    rnd = random.Random(3333); lines = {}
    for sid, fn in (("S-ana", "ana.txt"), ("S-ben", "ben.txt"), ("S-cy", "cy.txt")):
        txt = open(os.path.join(FIX, "sources", fn)).read(); lines[sid] = [l.split(": ", 1)[-1] for l in txt.splitlines() if len(l.split(": ", 1)[-1]) > 12]
    bad = []
    for i in range(30):
        p = copy.deepcopy(BASE); nopt = rnd.randint(2, 4); p["options"] = [{"id": "o%d" % n, "label": "Option %d" % n} for n in range(nopt)]
        ws = [rnd.randint(1, 8) for _ in range(3)]; tot_w = sum(ws); w = [D(x * 100 // tot_w) / 100 for x in ws]; w[-1] = D(1) - sum(w[:-1])
        p["dimensions"] = [{"id": "d%d" % n, "label": "Dim %d" % n, "weight": str(w[n])} for n in range(3)]
        p["sources"] = [s for s in p["sources"] if s["id"] in lines]; p["claims"] = []; sc = {}; n = 0
        for o in range(nopt):
            for d in range(3):
                for _ in range(rnd.choice([0, 1, 1, 2, 3])):
                    n += 1; sid = rnd.choice(sorted(lines)); s = rnd.randint(0, 5); cf = rnd.choice(["low", "medium", "high"]); seg = rnd.choice(["mid-size clinics"] * 4 + ["enterprise hospital system"])
                    p["claims"].append({"id": "K%d" % n, "option": "o%d" % o, "dimension": "d%d" % d, "source": sid, "segment": seg, "confidence": cf, "score": str(s), "quote": rnd.choice(lines[sid])})
                    if seg == "mid-size clinics": sc.setdefault(("o%d" % o, "d%d" % d), []).append((D(s), cf))
        tot, pref = model(p, sc); k = Pkg(p); rc, j = k.decide(); k.close()
        if not (same_totals(tot, tool_totals(j)) and j.get("preferred") == pref and rc == (0 if pref else 1)):
            bad.append({"i": i, "rc": rc, "pref": j.get("preferred"), "mine": pref, "got": j.get("totals"), "mine_t": {o: [str(q4(x)) if x is not None else None for x in v] for o, v in tot.items()}})
    row("E09 seeded soak: 30 random packages (2-4 options, random weights, scores, confidences, out-of-ICP claims, real quotes) match the independent model exactly", not bad, {"bad": bad[:2]})

for f in (e01, e02, e03, e04, e05, e06, e07, e08, e09): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
n = sum(r["pass"] for r in ROWS); print("M33 ORACLE %d/%d core %s" % (n, len(ROWS), "PASS" if n == len(ROWS) else "FAIL"))
