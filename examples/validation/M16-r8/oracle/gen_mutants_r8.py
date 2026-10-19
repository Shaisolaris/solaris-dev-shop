"""M16 r8 (Grok self-validation): materialise the BUILDER's r8 mutant edits (builder_mutants_r8.py, copied unchanged) without running
the builder's loop: exec only its definitions up to os.makedirs, then write MUTDIR/<name>/grounded_eval.py. Usage: PY gen_mutants_r8.py TREE MUTDIR"""
import os, sys
here = os.path.dirname(os.path.abspath(__file__)); tree, mut = sys.argv[1], sys.argv[2]
code = open(os.path.join(here, "builder_mutants_r8.py")).read(); code = code[:code.index("os.makedirs(out")]
ns = {}; sys.argv = ["x", tree, "/nonexistent"]; exec(compile(code, "builder_mutants_r8.py", "exec"), ns)
src, M = ns["src"], ns["M"]
for name, (a, b) in M.items():
    c = src.count(a)
    if c != 1: print(name, "ANCHOR-NOT-FOUND", c); continue
    os.makedirs(os.path.join(mut, name), exist_ok=True)
    open(os.path.join(mut, name, "grounded_eval.py"), "w", encoding="utf-8").write(src.replace(a, b)); print(name, "written")
