#!/usr/bin/env python3
"""M15 teeth (Grok self-validation): builder G15 mutants copied unchanged from G15/scripts/mutants.py, each applied to
a private copy of the candidate tree and scored by the M15 oracle. Kill = any core row result change or OBS detail change
versus the unmutated baseline. Usage: PY m15_teeth.py SRC_TREE MUTANTS.py ORACLE.py OUTDIR"""
import json, shutil, subprocess, sys, tempfile, runpy
from pathlib import Path
src, mfile, oracle, outd = [Path(x) for x in sys.argv[1:5]]; outd.mkdir(parents=True, exist_ok=True)
M = runpy.run_path(str(mfile))["M"]; PY = sys.executable
top = Path(tempfile.mkdtemp(prefix="m15teeth-", dir="/tmp"))
def score(tree, name):
    o = outd / (name + ".json"); subprocess.run([PY, str(oracle), str(tree), str(o)], capture_output=True, timeout=500)
    return {r["id"]: (r["result"], json.dumps(r["detail"], sort_keys=True, default=str) if r["kind"] == "OBS" else "") for r in json.load(open(o))}
base_tree = top / "base"; shutil.copytree(src, base_tree, ignore=shutil.ignore_patterns(".git", "__pycache__"))
base = score(base_tree, "baseline"); lines = []; kills = 0
for name, rel, old, new in M:
    t = top / name; shutil.copytree(base_tree, t); f = t / rel; s = f.read_text(); n = s.count(old)
    if n != 1: lines.append("%s NOT_APPLIED occurrences=%d" % (name, n)); shutil.rmtree(t); continue
    f.write_text(s.replace(old, new)); r = score(t, name); shutil.rmtree(t)
    ch = sorted(k for k in set(base) | set(r) if base.get(k) != r.get(k)); k = bool(ch); kills += k
    lines.append("%s %s %s" % (name, "KILLED" if k else "SURVIVED", ",".join(ch)))
shutil.rmtree(top, ignore_errors=True)
lines.append("TEETH %d/%d killed (python %s)" % (kills, len(M), sys.version.split()[0]))
(outd / "tally.txt").write_text("\n".join(lines) + "\n"); print("\n".join(lines))
