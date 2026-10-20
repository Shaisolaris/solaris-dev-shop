"""M15 r5 teeth (Grok self-validation): put each part of the G15 r5 fix back out; G15 tests and the M15 r5 probe score each.
Usage: m15r5_teeth.py CANDIDATE_DIR PROBE OUT"""
import os, shutil, subprocess, sys, tempfile
SRC, PROBE, OUT = sys.argv[1:4]
T = "employees/data/data-scientist/experiment_readout.py"
MUT = {
    "count_not_compared": ('"verified": checked > 0 and not mism and (eu is None or eu == in_window)}', '"verified": checked > 0 and not mism}'),
    "only_short_logs_fail": ("(eu is None or eu == in_window)}", "(eu is None or eu <= in_window)}"),
    "gap_not_stated": ('" (units missing from the log cannot be detected without randomization.expected_units; differential loss is guarded only by SRM)"', '""'),
    "multi_arm_units_not_counted": ("            in_window += 1\n            if len(arms_of[u]) > 1:\n                continue", "            if len(arms_of[u]) > 1:\n                continue\n            in_window += 1"),
    "bool_accepted": ('(isinstance(eu, bool) or not isinstance(eu, int) or eu < 1)', '(not isinstance(eu, int) or eu < 1)'),
}
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1"); out = []
for name, (a, b) in MUT.items():
    d = tempfile.mkdtemp(prefix="m15r5t-")
    try:
        shutil.copytree(SRC, d + "/c", ignore=shutil.ignore_patterns(".git"))
        p = d + "/c/" + T; s = open(p).read(); assert s.count(a) == 1, name; open(p, "w").write(s.replace(a, b))
        t = subprocess.run([sys.executable, "-m", "unittest", "tests.test_g15_capability"], cwd=d + "/c", capture_output=True, text=True, env=env, timeout=1200)
        o = subprocess.run([sys.executable, PROBE, d + "/c", d + "/o.json"], capture_output=True, text=True, env=env, timeout=1200)
        tl = (t.stderr.strip().splitlines() or ["?"])[-1]; ol = (o.stdout.strip().splitlines() or ["?"])[-1]
        fails = [l.split()[0] for l in o.stdout.splitlines() if " FAIL " in l]
        out.append("%s | G15 tests: %s (%s) | M15 r5 probe: %s %s" % (name, "CAUGHT" if t.returncode else "survived", tl, ol, fails))
    finally:
        shutil.rmtree(d, ignore_errors=True)
open(OUT, "w").write("\n".join(out) + "\n"); print("\n".join(out))
