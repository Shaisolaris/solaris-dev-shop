#!/usr/bin/env python3
"""M01 r4: distinguishing inputs for the two survivors (Grok self-validation). Usage: PY survivor_distinguish_r4.py"""
import json, os, shutil, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__)); E = "/tmp/m01r4-eval/employees/quality-security/assurance/quality_os.py"
d = tempfile.mkdtemp(prefix="m01r4-dist-", dir="/tmp")
OK = "General information only. This is not legal advice; consult a licensed attorney in your jurisdiction."
RC = {"gate": "security", "role": "security-auditor", "summary": "STRIDE review", "artifacts": ["reports/threat-model.md"], "blocking_open": 0}
cases = {"r4_marker_no_legal_text": {"legal_text": OK, "requested_actions": ["summarize the statute"]},
         "r4_marker_no_evidence": {"evidence": {"security": RC}, "requested_actions": ["summarize the statute"]}}
for name, pkt in cases.items():
    m = os.path.join(d, name + ".py"); subprocess.run([sys.executable, os.path.join(here, "make_mutants_r4.py"), E, name, m], check=True)
    f = os.path.join(d, name + ".json"); json.dump(pkt, open(f, "w")); out = {}
    for tag, eng in (("base", E), ("mutant", m)):
        cp = subprocess.run([sys.executable, eng, "run", f], capture_output=True, text=True, cwd=d)
        try: j = json.loads(cp.stdout); out[tag] = (cp.returncode, j.get("ok"), j.get("gate_codes"))
        except ValueError: out[tag] = (cp.returncode, cp.stdout[-80:])
    print(name, "DIFFERENT" if out["base"] != out["mutant"] else "SAME", json.dumps(out))
shutil.rmtree(d)
