#!/usr/bin/env python3
"""M33 r4 probe (Grok self-validation, not independent review). Written for this pass from the M33 r3 OBS rows
(18% vs "18 %", 18 vs European 18.000) and the G33 r5 doc. Unit rows call _value_in_quote; a regression row runs
`decide --json` on the shipped fixture and compares it with G33 r4. Inputs chosen here.
Usage: PY m33r4_probe.py REPO OUT.json [R4_REPO]"""
import importlib.util, json, os, subprocess, sys
REPO = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; R4 = sys.argv[3] if len(sys.argv) > 3 else None
REL = "employees/product-project/product-manager/evidence_decision.py"
spec = importlib.util.spec_from_file_location("ed", os.path.join(REPO, REL)); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
def row(rid, name, ok, detail, obs=False): ROWS.append({"row": rid, "name": name, "pass": bool(ok), "obs": obs, "detail": detail})
def table(cases):
    bad = {"%r in %r" % (v, q): m._value_in_quote(v, q) for v, q, want in cases if m._value_in_quote(v, q) != want}
    return bad
b = table([("7%", "conversion 7 % higher", True), ("7%", "conversion 7\u00a0% higher", True), ("7%", "conversion 7\u202f% higher", True),
           ("3.5%", "a 3,5 % drop", False), ("3.5%", "a 3.5 % drop", True), ("40%", "40 %, then 45 %", True), ("45%", "40 %, then 45 %", True)])
row("R01", "a percent after one space (plain, no-break, narrow no-break) matches the percent value; 3,5 % is not 3.5%", not b, b or "all")
b = table([("7", "conversion 7 % higher", False), ("7", "conversion 7\u00a0% higher", False), ("40", "40 %, then 45 %", False), ("7", "rank 7 of 10", True)])
row("R02", "a plain value no longer matches a number the quote writes as a percent after a space (fails closed)", not b, b or "all")
b = table([("7%", "up 17 % in May", False), ("7%", "up 7.5 % in May", False), ("1,000", "1,000 % growth", False), ("1,000%", "1,000 % growth", True)])
row("R03", "boundaries hold with the space: 7% never matches 17 % or 7.5 %; grouped numbers keep their percent", not b, b or "all")
b = table([("18", "Umsatz 18.000 Euro", True), ("18000", "Umsatz 18.000 Euro", False), ("18000", "revenue 18,000 dollars", True)])
row("R04", "the documented decimal-point convention: 18.000 reads as 18 (as the doc now says), 18,000 as eighteen thousand", not b, b or "all")
doc = open(os.path.join(REPO, "employees/product-project/product-manager/evidence-product-decision.md")).read()
row("R05", "the doc states the percent-after-space rule and the decimal-point convention", "`18%` matches `18 %`" in doc and "`.` is read as a decimal point" in doc, None)
w = m._value_in_quote("7%", "conversion 7\u2009% higher")
row("R06", "OBS: a thin space (U+2009) before % is not one of the accepted spaces", True, {"7% in '7<thin space>%'": w}, obs=True)
if R4:
    def decide(repo):
        r = subprocess.run([sys.executable, os.path.join(repo, REL), "decide", os.path.join(repo, "examples/capabilities/G33/fixtures/choice.json"), "--json"],
                           capture_output=True, text=True, env=ENV, timeout=300, cwd=repo)
        j = json.loads(r.stdout); j.pop("package_sha256", None); return r.returncode, j
    a, b2 = decide(REPO), decide(R4)
    row("R07", "regression: decide --json on the shipped fixture equals G33 r4", a == b2, {"rc": [a[0], b2[0]], "equal": a == b2})
for r in ROWS: print(r["row"], "OBS " if r["obs"] else ("PASS" if r["pass"] else "FAIL"), r["name"], "|", json.dumps(r["detail"])[:300])
sc = [r for r in ROWS if not r["obs"]]; n = sum(r["pass"] for r in sc); print("M33R4 PROBE %d/%d" % (n, len(sc)))
json.dump(ROWS, open(OUT, "w"), indent=1); sys.exit(0 if n == len(sc) else 1)
