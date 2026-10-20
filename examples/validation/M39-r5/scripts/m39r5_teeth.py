"""M39 r5 teeth (Grok self-validation): take each part of the G39 r5 fix back out; the G39 tests and the M39 r5 probes
score each mutant. Usage: m39r5_teeth.py CANDIDATE_DIR ORACLE_DIR OUT"""
import os, shutil, subprocess, sys, tempfile
SRC, OD, OUT = sys.argv[1:4]
T = "employees/product-project/delivery-lead/delivery_evidence.py"
MUT = {
    "rewrite_never_recorded": ('"inputs_rewritten_during_run": rewritten[:50],', '"inputs_rewritten_during_run": [],'),
    "verify_ignores_rewrite": ('    if rewritten:  # r5', '    if False:  # r5'),
    "every_change_is_a_rewrite": ('    return [k for k in touched if k in before and not (k.endswith("-shm") and k[:-4] in after)]', '    return list(touched)'),
    "all_sidecars_exempt": ('not (k.endswith("-shm") and k[:-4] in after)', 'not k.endswith(("-shm", "-wal", "-journal"))'),
    "rewrite_gap_dropped_unless_exit_1": ('    if gap_kinds:\n', '    if gap_kinds == ["exit_1"]:\n'),
    "strict_is_default_mapping": ('    if ns.strict:\n        return {', '    if False:\n        return {'),
    "strict_gaps_exit_0": ('"GO_WITH_GAPS": 3, "EVIDENCED_NO_ORDER": 4}', '"GO_WITH_GAPS": 0, "EVIDENCED_NO_ORDER": 4}'),
    "default_mapping_changed": ('    return 1 if rep["verdict"] == "NO_GO" else 0\n', '    return 0 if rep["verdict"] == "GO" else 1\n'),
}
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); out = []
for name, (a, b) in MUT.items():
    d = tempfile.mkdtemp(prefix="m39r5t-")
    try:
        shutil.copytree(SRC, d + "/c", ignore=shutil.ignore_patterns(".git"))
        p = d + "/c/" + T; s = open(p).read(); assert s.count(a) == 1, name; open(p, "w").write(s.replace(a, b))
        t = subprocess.run([sys.executable, "-m", "unittest", "tests.test_g39_capability"], cwd=d + "/c", capture_output=True, text=True, env=env, timeout=1200)
        o = subprocess.run([sys.executable, os.path.join(OD, "m39r5_probe.py"), d + "/c", d + "/o.json"], capture_output=True, text=True, env=env, timeout=1200)
        fails = [l.split()[1] for l in o.stdout.splitlines() if l.startswith("FAIL")]
        out.append("%s | G39 tests: %s | %s %s" % (name, "CAUGHT" if t.returncode else "survived", (o.stdout.strip().splitlines() or ["?"])[-1], fails))
    finally:
        shutil.rmtree(d, ignore_errors=True)
open(OUT, "w").write("\n".join(out) + "\n"); print("\n".join(out))
