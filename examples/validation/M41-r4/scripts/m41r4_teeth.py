"""M41 r4 teeth (Grok self-validation): mutate G41 r4's two fixes back out and check the G41 tests and the
M41 oracle catch each one. Usage: m41r4_teeth.py CANDIDATE_DIR M41_ORACLE OUT"""
import os, shutil, subprocess, sys, tempfile
SRC, ORA, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
T = "employees/quality-security/assurance/release_candidate.py"
MUT = {
    "keep_unselected_blocking": ("    return goals, gate, unselected - set(req)", "    return goals, gate, set()"),
    "ignore_newer_heads": ("        if any(k is True for k in known):", "        if False:"),
    "any_differing_head_is_newer": ("        if any(k is True for k in known):", "        if any(k is not None for k in known):"),
    "ignore_unknown_heads": ("        elif any(k is None for k in known):", "        elif False:"),
    "word_match_substring": ('    word = re.compile(r"(^|[/_-])%s($|[/_-])" % re.escape(gid.lower()))', '    word = re.compile(re.escape(gid.lower()[:2]))'),
}
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
lines = []
for name, (a, b) in MUT.items():
    d = tempfile.mkdtemp(prefix="m41r4-")
    try:
        shutil.copytree(SRC, d + "/c", ignore=shutil.ignore_patterns(".git"))
        p = d + "/c/" + T; s = open(p).read(); assert s.count(a) == 1, name
        open(p, "w").write(s.replace(a, b))
        t = subprocess.run([sys.executable, "-m", "unittest", "tests.test_g41_capability"], cwd=d + "/c", capture_output=True, text=True, env=env, timeout=900)
        o = subprocess.run([sys.executable, ORA, d + "/c", d + "/o.json"], capture_output=True, text=True, env=env, timeout=900)
        tl = (t.stderr.strip().splitlines() or ["?"])[-1]; ol = (o.stdout.strip().splitlines() or ["?"])[-1]
        caught = t.returncode != 0
        lines.append("%s | G41 tests: %s (%s) | M41 oracle: %s" % (name, "CAUGHT" if caught else "SURVIVED", tl, ol))
    finally:
        shutil.rmtree(d, ignore_errors=True)
open(OUT, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
