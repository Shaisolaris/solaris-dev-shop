#!/usr/bin/env python3
"""M38 r3 probe (Grok self-validation, not independent review). Restrictions placed in the MIT copyright line that the
r3 holder guard (a word list) does not name. Each case copies the G38 clean fixture repository, replaces the LICENSE
copyright line, and runs the real CLI: a restriction must not come out as MIT/consistent. R rows scored, C rows are
controls that must stay MIT. Usage: PY m38r3_probe.py TREE OUT.json"""
import json, os, re, shutil, subprocess, sys, tempfile
TREE = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; PY = sys.executable
TOOL = os.path.join(TREE, "employees/quality-security/security-auditor/provenance_check.py")
FIX = os.path.join(TREE, "examples/capabilities/G38/fixtures/repo-clean")
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ROWS = []
CASES = [
    ("C1 plain holder stays MIT", "Copyright (c) 2026 Oracle Test Holdings", True),
    ("C2 holder with all rights reserved stays MIT", "Copyright (c) 2025-2026 Oracle Test Holdings. All rights reserved.", True),
    ("R1 'noncommercial' (one word) in the holder", "Copyright (c) 2026 Oracle Test Holdings, noncommercial purposes", False),
    ("R2 'cannot be resold'", "Copyright (c) 2026 Oracle Test Holdings, which cannot be resold", False),
    ("R3 'for academic research purposes exclusively'", "Copyright (c) 2026 Oracle Test Holdings, for academic research purposes exclusively", False),
    ("R4 'personal usage'", "Copyright (c) 2026 Oracle Test Holdings, personal usage", False),
    ("R5 'redistribution never allowed'", "Copyright (c) 2026 Oracle Test Holdings, redistribution never allowed", False),
    ("R6 guarded word still caught: 'commercial use prohibited'", "Copyright (c) 2026 Oracle Test Holdings, commercial use prohibited", False),
]
for name, line, want_mit in CASES:
    t = tempfile.mkdtemp(prefix="m38r3-"); d = os.path.join(t, "r")
    try:
        shutil.copytree(FIX, d)
        lic = open(os.path.join(d, "LICENSE")).read().splitlines()
        i = next(k for k, l in enumerate(lic) if l.lower().startswith("copyright"))
        lic[i] = line; open(os.path.join(d, "LICENSE"), "w").write("\n".join(lic) + "\n")
        if os.path.exists(os.path.join(d, "MANIFEST.sha256")): os.remove(os.path.join(d, "MANIFEST.sha256"))
        r = subprocess.run([PY, TOOL, "check", d, "--json"], capture_output=True, text=True, env=ENV, timeout=120)
        try: doc = json.loads(r.stdout)
        except ValueError: doc = {}
        mit = doc.get("license") == "MIT" and doc.get("result") == "consistent" and r.returncode == 0
        ok = mit if want_mit else not mit
        ROWS.append({"row": name, "pass": ok, "detail": {"rc": r.returncode, "license": doc.get("license"), "result": doc.get("result"),
                                                       "codes": [f.get("code") for f in doc.get("findings", [])][:4], "line": line}})
        print(("PASS " if ok else "FAIL ") + name + " " + json.dumps({"rc": r.returncode, "license": doc.get("license"), "result": doc.get("result")}))
    finally:
        shutil.rmtree(t, ignore_errors=True)
json.dump({"rows": ROWS}, open(OUT, "w"), indent=1)
print("M38R3 PROBES %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
