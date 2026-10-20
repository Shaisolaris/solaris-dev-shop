#!/usr/bin/env python3
"""M42 probe (Grok self-validation, not independent review). Written from the G42 cross_checks.py docstring and the
G42 README: each cross-check must report a finding when the thing it guards is broken on a copy of the integrated
tree, and no unrelated check should fire (x1 may also fire when the broken tool is one the G39 drill runs). P rows are scored. Usage: PY m42_probe.py SRC OUT.json"""
import json, os, re, shutil, subprocess, sys, tempfile
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; PY = sys.executable; ROWS = []
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); ENV.pop("G20_CHROME", None)

def copy():
    t = tempfile.mkdtemp(prefix="m42p-"); d = os.path.join(t, "r")
    shutil.copytree(SRC, d, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    return t, d

def edit(d, rel, fn):
    p = os.path.join(d, rel); s = open(p, encoding="utf-8").read(); n = fn(s)
    assert n != s, rel; open(p, "w", encoding="utf-8").write(n)

def cross(d):
    r = subprocess.run([PY, "examples/capabilities/G42/cross_checks.py"], cwd=d, capture_output=True, text=True, env=ENV, timeout=900)
    f = [l for l in r.stdout.splitlines() if l.startswith("FINDING ")]
    return r.returncode, sorted({l.split()[1] for l in f}), f

CASES = [
    ("P0 clean copy: no finding", None, []),
    ("P1 x1 fires when the G04 handoff tool is broken (drill cannot pass)",
     lambda d: edit(d, "employees/infrastructure/fleet-dispatcher/handoff.py", lambda s: s.replace("\nimport ", "\nimport sys as _m42; _m42.exit(9)\nimport ", 1)), ["x1"]),
    ("P2 x2 fires when pyproject declares a different license from LICENSE and the plugins",
     lambda d: edit(d, "pyproject.toml", lambda s: re.sub(r'(?m)^(license\s*=\s*.*?)MIT', r'\1Apache-2.0', s, count=1)), ["x2"]),
    ("P3 x3 fires when a security-auditor script listed in its contract is missing",
     lambda d: os.remove(os.path.join(d, "employees/quality-security/security-auditor/boundary_probe.py")), ["x3"], {"x1"}),
    ("P4 x3 fires when a listed script does not compile",
     lambda d: open(os.path.join(d, "employees/quality-security/security-auditor/boundary_probe.py"), "a").write("\ndef (:\n"), ["x3"], {"x1"}),
    ("P5 x4 fires when the legal-advisor contract stops naming the G38 test",
     lambda d: edit(d, "employees/legal-compliance/legal-advisor/capability.contract.json", lambda s: s.replace("tests/test_g38_capability.py", "tests/test_g38_capability_gone.py")), ["x4"]),
    ("P6 x4 fires when the G37 report drops its not-legal-advice statement",
     lambda d: edit(d, "employees/legal-compliance/compliance-auditor/privacy_inventory.py", lambda s: s.replace('"not_legal_advice": NOT_ADVICE', '"not_legal_advice": ""', 1)), ["x4"]),
]
for case in CASES:
    name, mut, want = case[:3]; also = case[3] if len(case) > 3 else set()
    t, d = copy()
    try:
        if mut: mut(d)
        rc, ids, f = cross(d)
        ok = (rc == (1 if want else 0)) and set(want) <= set(ids) and set(ids) <= set(want) | also
        ROWS.append({"row": name, "pass": ok, "detail": {"rc": rc, "fired": ids, "want": want, "may_also_fire": sorted(also), "findings": [x[:220] for x in f]}})
        print(("PASS " if ok else "FAIL ") + name + " " + json.dumps({"rc": rc, "fired": ids}), flush=True)
    except Exception as e:
        ROWS.append({"row": name + " crash", "pass": False, "detail": {"crash": repr(e)[:300]}}); print("FAIL " + name + " crash " + repr(e)[:200])
    finally:
        shutil.rmtree(t, ignore_errors=True)
json.dump({"rows": ROWS}, open(OUT, "w"), indent=1)
print("M42 PROBES %d/%d" % (sum(r["pass"] for r in ROWS), len(ROWS)))
