#!/usr/bin/env python3
"""M37 h1 doc probe (Grok self-validation, not independent review; not legal advice). Checks the compliance-auditor
role files for the corrected GDPR Art. 12(3) wording and the tool's month clock. Usage: PY m37h1_doc_probe.py TREE OUT.json"""
import datetime as dt, importlib.util, json, os, re, sys
T = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; R = "employees/legal-compliance/compliance-auditor/"; rows = []
def row(n, ok, d=None): rows.append({"row": n, "pass": bool(ok), "detail": d}); print(("PASS " if ok else "FAIL ") + n, d if d is not None else "")
txt = {f: open(os.path.join(T, R, f), encoding="utf-8").read() for f in ("SKILL.md", "rules.md", "learnings.md")}
for f in ("SKILL.md", "rules.md"):
    hits = [l.strip()[:90] for l in txt[f].splitlines() if re.search(r"30-day", l, re.I) and "not a fixed 30" not in l]
    row(f + ": no 30-day DSAR clock left", not hits, hits)
    row(f + ": states one month and the two-month extension with Art. 12(3)", re.search(r"one month", txt[f]) and re.search(r"two further months", txt[f]) and "12(3)" in txt[f])
row("SKILL.md: says the extension needs notice within the first month with reasons", re.search(r"within the first month with reasons", txt["SKILL.md"]))
row("learnings.md: pending note records the correction", "Corrected in G37 h1" in txt["learnings.md"])
spec = importlib.util.spec_from_file_location("pi", os.path.join(T, R, "privacy_inventory.py")); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cases = [((2026, 1, 31), (2026, 2, 28)), ((2028, 1, 31), (2028, 2, 29)), ((2026, 3, 15), (2026, 4, 15)), ((2026, 12, 31), (2027, 1, 31))]
for a, b in cases:
    got = m.due_from(dt.datetime(*a), {"months": 1, "source": "x"})
    row("tool month clock %s + 1 month = %s" % (dt.date(*a), dt.date(*b)), got.date() == dt.date(*b), str(got.date()))
json.dump({"rows": rows}, open(OUT, "w"), indent=1)
print("M37H1 DOC PROBE %d/%d" % (sum(r["pass"] for r in rows), len(rows)))
