#!/usr/bin/env python3
"""Grok self-validation: for each named survivor, apply the builder mutant to a private copy and run the builder's goal
test module. Usage: PY survivor_builder_tests.py SRC MUTANTS.py TESTMODULE OUT NAME..."""
import runpy, shutil, subprocess, sys, tempfile
from pathlib import Path
src, mf, mod, out = sys.argv[1:5]; names = sys.argv[5:]; M = {m[0]: m for m in runpy.run_path(mf)["M"]}; lines = []
for n in names:
    _, rel, old, new = M[n]; t = Path(tempfile.mkdtemp(prefix="survbt-", dir="/tmp")) / "c"; shutil.copytree(src, t, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    f = t / rel; f.write_text(f.read_text().replace(old, new, 1))
    p = subprocess.run([sys.executable, "-m", "unittest", mod], cwd=t, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(t.parent)}, timeout=550)
    tail = p.stderr.strip().splitlines()[-1] if p.stderr.strip() else ""; fails = [l for l in p.stderr.splitlines() if l.startswith(("FAIL:", "ERROR:"))]
    lines.append("%s builder tests: %s %s" % (n, "KILL" if p.returncode else "no kill", tail + " " + "; ".join(fails))); shutil.rmtree(t.parent)
open(out, "w").write("\n".join(lines) + "\n"); print("\n".join(lines))
