# M09 (Grok self-validation): for each named survivor, apply the builder mutant to a fresh copy and run the builder's
# tests.test_g09_capability, to show whether the survivor is non-equivalent. Usage: PY survivor_builder_tests.py SRC MUTANTS.py NAME...
import runpy, shutil, subprocess, sys, tempfile
from pathlib import Path
src, mf = Path(sys.argv[1]), sys.argv[2]; M = {m[0]: m for m in runpy.run_path(mf)["M"]}
for n in sys.argv[3:]:
    t = Path(tempfile.mkdtemp(prefix="m09surv-", dir="/tmp")) / "r"; shutil.copytree(src, t, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    _, f, a, b = M[n]; p = t / f; s = p.read_text(); p.write_text(s.replace(a, b, 1))
    cp = subprocess.run([sys.executable, "-m", "unittest", "tests.test_g09_capability"], cwd=t, capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(t.parent)})
    print(n, "builder tests rc", cp.returncode, cp.stderr.strip().splitlines()[-1] if cp.stderr.strip() else ""); shutil.rmtree(t.parent)
