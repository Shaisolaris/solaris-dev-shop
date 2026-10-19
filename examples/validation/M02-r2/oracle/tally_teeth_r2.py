"""Tally M02 r2 teeth against the candidate's own baseline (the candidate fails C06 with 6 unbounded cases,
so a mutant is killed only by a new failing check or by more C06 unbounded cases than the candidate).
Usage: python tally_teeth_r2.py RESULTS_DIR"""
import re, sys
from pathlib import Path
R = Path(sys.argv[1])
def parse(p):
    t = p.read_text(); fails = set(re.findall(r"^FAIL (C\d+)", t, re.M))
    m = re.search(r"^FAIL C06\S* \([^)]*\): (\d+) unbounded", t, re.M)
    return fails, int(m.group(1)) if m else (0 if "C06" not in fails else -1)
base_f, base_n = parse(R / "oracle-candidate-3.12.14.txt")
print(f"candidate baseline: failing {sorted(base_f)} C06 unbounded {base_n}")
k = 0; rows = sorted((R / "teeth").glob("oracle-*.txt"))
for p in rows:
    f, n = parse(p); new = sorted(f - base_f); more = n > base_n or n == -1
    b = (R / "teeth" / p.name.replace("oracle-", "builder-")).read_text().strip().splitlines()[-1]
    killed = bool(new) or more; k += killed
    print(f"{p.stem[7:]:24s} {'KILLED' if killed else 'SURVIVED'} new_failing={new} C06_unbounded={n} builder_tests={b}")
print(f"TEETH my oracle kills {k}/{len(rows)}")
