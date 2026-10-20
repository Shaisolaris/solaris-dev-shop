"""M39 r4 teeth (Grok self-validation): take each part of the G39 r4 fix back out; G39 tests, the M39 r3 probes and the
M39 r4 probes score each. Usage: m39r4_teeth.py CANDIDATE_DIR ORACLE_DIR OUT"""
import os, shutil, subprocess, sys, tempfile
SRC, OD, OUT = sys.argv[1:4]
T = "employees/product-project/delivery-lead/delivery_evidence.py"
MUT = {
    "lexical_normpath_not_realpath": ("a = Path(os.path.realpath(j)).relative_to(base).as_posix()", "a = Path(os.path.normpath(j)).relative_to(base).as_posix()"),
    "dotdot_branch_removed": ('        elif ".." in Path(a).parts:', '        elif False:'),
    "unbound_not_recorded": ('"unbound_inputs": unbound_inputs,', '"unbound_inputs": [],'),
    "verify_does_not_surface": ('    if r.get("unbound_inputs"):\n        out["unbound_inputs"]', '    if False:\n        out["unbound_inputs"]'),
}
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); out = []
for name, (a, b) in MUT.items():
    d = tempfile.mkdtemp(prefix="m39r4t-")
    try:
        shutil.copytree(SRC, d + "/c", ignore=shutil.ignore_patterns(".git"))
        p = d + "/c/" + T; s = open(p).read(); assert s.count(a) == 1, name; open(p, "w").write(s.replace(a, b))
        t = subprocess.run([sys.executable, "-m", "unittest", "tests.test_g39_capability"], cwd=d + "/c", capture_output=True, text=True, env=env, timeout=1200)
        res = []
        for pr in ("m39r3_probe.py", "m39r4_probe.py"):
            o = subprocess.run([sys.executable, os.path.join(OD, pr), d + "/c", d + "/o.json"], capture_output=True, text=True, env=env, timeout=1200)
            res.append("%s %s" % ((o.stdout.strip().splitlines() or ["?"])[-1], [l.split()[1] for l in o.stdout.splitlines() if l.startswith("FAIL")]))
        out.append("%s | G39 tests: %s | %s" % (name, "CAUGHT" if t.returncode else "survived", " | ".join(res)))
    finally:
        shutil.rmtree(d, ignore_errors=True)
open(OUT, "w").write("\n".join(out) + "\n"); print("\n".join(out))
