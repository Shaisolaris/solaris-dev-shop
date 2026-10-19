#!/usr/bin/env python3
"""M15 r3 probe (Grok self-validation): regenerate the r2 drift oracle's D06 property cases (same seeds and generator,
copied from m15r2_drift.py) and apply my r3 scan rule (m15r3_scan.scan) to each, to show whether the single r2-rule
mismatch on r3 is the documented r3 scan and nothing else. Usage: PY d06_under_r3_rule.py"""
import ast, random, sys, types
from datetime import timedelta
from pathlib import Path
here = Path(__file__).resolve().parent.parent / "oracle"
def load(name, keep):
    src = (here / name).read_text(); tree = ast.parse(src); body = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) or (isinstance(n, ast.FunctionDef) and n.name in keep) or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("CS", "H", "_PV") for t in n.targets))]
    mod = types.ModuleType(name); exec(compile(ast.Module(body=body, type_ignores=[]), name, "exec"), mod.__dict__); return mod
r2 = load("m15r2_drift.py", {"gen", "sf", "expected"}); r3 = load("m15r3_scan.py", {"scan", "binom_p", "sf"})
r = random.Random(50)
for k in range(30):
    shape = r.choice(["none", "step", "osc", "spike", "gradual"]); days = r.choice([21, 28, 35, 49]); per = r.choice([8, 15, 30])
    a0 = r.choice([0.5, 0.45]); amp = r.choice([0.03, 0.08, 0.15]); sd = r.randint(0, days - 1)
    fn = {"none": lambda d: 0.5, "step": lambda d: a0 if d < sd else 1 - a0, "osc": lambda d: 0.5 + amp * (1 if (d // 7) % 2 else -1),
          "spike": lambda d: 0.95 if d == sd else 0.5, "gradual": lambda d: 0.5 - amp + 2 * amp * d / days}[shape]
    us = r2.gen(random.Random(500 + k), days, fn, lambda d: 0.25, per)
    e2 = r2.expected(us, (0.5, 0.5), days); sc = r3.scan([("u%06d" % i, a, t) for i, (a, t, c) in enumerate(us)], (0.5, 0.5))
    if sc["mismatch"] or k in (0,): print(k, shape, days, per, "r2-rule:", e2["outcome"], "| r3 scan mismatch:", sc["mismatch"], "min p %.3e K %d" % (sc["min_p"], sc["K"]))
print("done")
