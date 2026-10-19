#!/usr/bin/env python3
"""M09 teeth (Grok self-validation): builder G09 mutants copied unchanged from G09/scripts/mutants.py, each applied to
a private copy of the candidate tree and scored by the M09 oracle. Kill = any core row result change or OBS detail change
versus the unmutated baseline. Mutants run JOBS at a time (default 6). Usage: PY m09_teeth.py SRC_TREE MUTANTS.py ORACLE.py OUTDIR [JOBS]"""
import json, shutil, subprocess, sys, tempfile, runpy
from pathlib import Path
src, mfile, oracle, outd = [Path(x) for x in sys.argv[1:5]]; outd.mkdir(parents=True, exist_ok=True)
M = runpy.run_path(str(mfile))["M"]; PY = sys.executable
top = Path(tempfile.mkdtemp(prefix="m09teeth-", dir="/tmp"))
def score(tree, name):
    o = outd / (name + ".json"); subprocess.run([PY, str(oracle), str(tree), str(o)], capture_output=True, timeout=500)
    return {r["id"]: (r["result"], json.dumps(r["detail"], sort_keys=True, default=str) if r["kind"] == "OBS" else "") for r in json.load(open(o))}
base_tree = top / "base"; shutil.copytree(src, base_tree, ignore=shutil.ignore_patterns(".git", "__pycache__"))
base = score(base_tree, "baseline")
from concurrent.futures import ThreadPoolExecutor
JOBS = int(sys.argv[5]) if len(sys.argv) > 5 else 6
def one(mu):
    name, rel, old, new = mu; t = top / name; shutil.copytree(base_tree, t); f = t / rel; s = f.read_text(); n = s.count(old)
    if n != 1: shutil.rmtree(t); return "%s NOT_APPLIED occurrences=%d" % (name, n), 0
    f.write_text(s.replace(old, new)); r = score(t, name); shutil.rmtree(t)
    ch = sorted(k for k in set(base) | set(r) if base.get(k) != r.get(k))
    return "%s %s %s" % (name, "KILLED" if ch else "SURVIVED", ",".join(ch)), int(bool(ch))
with ThreadPoolExecutor(JOBS) as ex: res = list(ex.map(one, M))
lines = [a for a, _ in res]; kills = sum(b for _, b in res)
shutil.rmtree(top, ignore_errors=True)
lines.append("TEETH %d/%d killed (python %s)" % (kills, len(M), sys.version.split()[0]))
(outd / "tally.txt").write_text("\n".join(lines) + "\n"); print("\n".join(lines))
