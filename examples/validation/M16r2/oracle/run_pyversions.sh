#!/bin/zsh
# Usage: zsh run_pyversions.sh ORACLE_DIR RAW_DIR TREE PY...
# Per interpreter: G16 tests, the original 84, the full suite, the full m16_oracle (core + adversarial),
# and sha256 of baseline answers for the v1 world and a seeded bus world (cross-interpreter determinism).
O=$1; R=$2; C=$3; shift 3; export PYTHONDONTWRITEBYTECODE=1; T=employees/engineering/llm-agent-designer/grounded_eval.py
: > $R/pyversions-matrix.txt; : > $R/cross-interpreter-answers.txt
for py in $@; do v=$($py -c 'import sys;print(sys.version.split()[0])')
  S=/tmp/m16-suite-$v; rm -rf $S; rsync -a --exclude .git $C/ $S/; cd $S
  echo "=== $v" >> $R/pyversions-matrix.txt
  for pat in test_g16_capability.py 'test_[!g]*.py' 'test*.py'; do $py -m unittest discover -s tests -p "$pat" > $S.log 2>&1; echo "  pattern $pat: rc=$? $(grep -E '^(Ran|OK|FAILED|FAIL:|ERROR:)' $S.log | tr '\n' ' ')" >> $R/pyversions-matrix.txt; done
  echo "  candidate git status lines (worktree): $(cd $C && git status --porcelain | wc -l | tr -d ' ')" >> $R/pyversions-matrix.txt
  cd /tmp; rm -rf $S $S.log
  { echo "# m16_oracle on $v $(date '+%F %T %Z')"; $py $O/m16_oracle.py -- $py $C/$T; echo "[exit $?]"; } > $R/oracle-candidate-$v.txt 2>&1
  X=/tmp/m16-x-$v; rm -rf $X; mkdir -p $X; cd $X
  $py - $O <<'PY'
import sys; sys.path.insert(0, sys.argv[1]); import m16_world as W; from pathlib import Path
W.write_snapshot(Path("v1"), W.V1); W.write_questions(Path("q1.jsonl"), W.QV1)
d, q, _ = W.bus_world(424242, 200); W.write_snapshot(Path("bus"), d); W.write_questions(Path("qb.jsonl"), q)
PY
  $py $C/$T answer --corpus v1 --questions q1.jsonl --out a1.jsonl > /dev/null; $py $C/$T answer --corpus bus --questions qb.jsonl --out ab.jsonl --workers 4 > /dev/null
  $py $C/$T evaluate --corpus v1 --questions q1.jsonl --answers a1.jsonl --json --out r1.json > /dev/null
  echo "$v v1-answers $(shasum -a 256 a1.jsonl | cut -c1-16) bus-answers $(shasum -a 256 ab.jsonl | cut -c1-16) v1-report $(shasum -a 256 r1.json | cut -c1-16)" >> $R/cross-interpreter-answers.txt
  cd /tmp; rm -rf $X
done
echo PYV-DONE
