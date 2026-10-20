"""M33 r3 probe (Grok self-validation, not independent review). Usage: m33r3_probe.py WT [PY]"""
import hashlib, importlib.util, json, os, shutil, subprocess, sys, tempfile
WT = sys.argv[1]; PY = sys.argv[2] if len(sys.argv) > 2 else sys.executable
TOOL = os.path.join(WT, "employees/product-project/product-manager/evidence_decision.py")
FIX = os.path.join(WT, "examples/capabilities/G33/fixtures")
R = []
def rec(n, ok, d, obs=False): R.append((n, bool(ok), d, obs))
# unit level (only when the helper exists; r2 has no _value_in_quote and is scored at decide level only)
spec = importlib.util.spec_from_file_location("ed", TOOL); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
viq = getattr(m, "_value_in_quote", None) or (lambda v, q: v in q)
for n, v, q, want in (("E01 18 vs 18,000", "18", "clinics: 18,000.", False), ("E02 18000 vs 18,000", "18000", "clinics: 18,000.", True),
                      ("E04 1,5 vs 11,500", "1,5", "surveyed 11,500 clinics", False), ("E05 +18 vs +180", "+18", "growth of +180 seats", False),
                      ("E06 -5 vs -50", "-5", "a change of -50 points", False), ("E08 0.5 vs 10.5", "0.5", "about 10.5 hours", False),
                      ("E12 fullwidth 18 vs 18,000", "\uff11\uff18", "clinics: 18,000.", False)):
    got = viq(v, q); rec(n + " -> %s" % want, got == want, got)
for n, v, q in (("E03 18% vs '18 %'", "18%", "grew 18 % last year"), ("E07 18.0 vs 18", "18.0", "18 clinics"), ("E11 18 vs European 18.000", "18", "Kliniken: 18.000.")):
    rec("OBS " + n, True, viq(v, q), obs=True)
def decide(text, claim, quantity=False):
    d = tempfile.mkdtemp(); shutil.copytree(FIX, os.path.join(d, "fx")); fx = os.path.join(d, "fx")
    P = json.load(open(os.path.join(fx, "choice.json")))
    open(os.path.join(fx, "sources", "market.txt"), "w").write(text)
    s = [x for x in P["sources"] if x["id"] == "S-mkt"][0]; s["retrieved_at"] = "2026-09-20"
    s["snapshot"]["sha256"] = hashlib.sha256(open(os.path.join(fx, "sources", "market.txt"), "rb").read()).hexdigest()
    c = [x for x in P["claims"] if x["id"] == "C10"][0]; c.update(claim)
    if quantity: P["dimensions"][2]["quantity"] = True
    json.dump(P, open(os.path.join(fx, "choice.json"), "w"))
    r = subprocess.run([PY, TOOL, "decide", os.path.join(fx, "choice.json"), "--json"], capture_output=True, text=True)
    shutil.rmtree(d)
    try: j = json.loads(r.stdout)
    except Exception: j = {"_raw": (r.stdout + r.stderr)[-200:]}
    return r.returncode, sorted((f["code"], f["ref"]) for f in j.get("findings", [])), j
T = "Saved page.\nSurvey: clinics surveyed 11,500; seat growth +180; churn change -50 points.\n"
Q = "Survey: clinics surveyed 11,500; seat growth +180; churn change -50 points."
for n, val, sc in (("D09 value 1,5 from 11,500 (would score 3)", "1,5", "3"), ("D10 value +18 from +180 (score 3)", "+18", "3"), ("D11 value -5 from -50 (score 0)", "-5", "0")):
    rc, f, j = decide(T, {"quote": Q, "value": val, "score": sc})
    rec(n + " -> value_not_in_quote", ("value_not_in_quote", "C10") in f, (rc, f, j.get("_raw")))
rc, f, j = decide(T, {"quote": Q, "value": "11,500", "score": "5"})
rec("D12 value 11,500 score 5 -> no finding", rc in (0, 1) and f == [], (rc, f, j.get("_raw")))
rc, f, j = decide(T, {"quote": Q, "value": "1,5", "score": "3"}, quantity=True)
rec("D13 quantity dimension, value 1,5 from 11,500 -> value_not_in_quote", ("value_not_in_quote", "C10") in f, (rc, f))
for n, ok, d, obs in R: print("%s %s %s" % ("OBS " if obs else ("PASS" if ok else "FAIL"), n, d))
sc = [r for r in R if not r[3]]; print("PROBE %d/%d" % (sum(r[1] for r in sc), len(sc)))
