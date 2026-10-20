#!/usr/bin/env python3
"""Re-score M-K1 and M-K2 from the saved m20r2-browser.json (no browser). My first expectations were wrong against
the documented contract (async-search-ui.md): rows whose id or label is blank after trimming are dropped (13 rows ->
11) and labels are cut to 200 characters. Corrected: K1 wants 11 valid, resolving, unique ids; K2 wants the last row's
label cut to 200 characters. Usage: PY m20r2_rescore.py m20r2-browser.json"""
import json, re, sys
d = json.load(open(sys.argv[1])); VALID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$"); URL = "https://example.invalid/" + "segment/" * 25
out = []
for r in d["rows"]:
    if r["id"].startswith("M-K1-"):
        ids = r["detail"]; ok = len(ids) == 11 and len(set(ids)) == 11 and all(VALID.match(i or "") for i in ids)
        # the saved data holds only the ids: per-step resolve, CSS-selector and focus results were not stored for my rows,
        # so this corrected row checks validity and uniqueness only (the builder's K02 rows check resolving in the same session)
        out.append({"id": r["id"] + "c", "pass": ok, "desc": "11 kept rows (2 blank ids dropped as documented): ids valid and unique", "detail": ids})
    elif r["id"].startswith("M-K2-"):
        out.append({"id": r["id"] + "c", "pass": r["detail"] == [URL[:200]], "desc": "ArrowUp from the first option wraps to the last (label cut to 200 as documented)", "detail": len(r["detail"][0])})
    else:
        out.append(r)
for r in out: print(r["id"], "PASS" if r["pass"] else "FAIL", r["desc"])
print("M20R2 BROWSER PROBE (rescored) %d/%d" % (sum(r["pass"] for r in out), len(out)))
