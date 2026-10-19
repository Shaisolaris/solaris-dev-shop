#!/bin/zsh
# M20 (Grok self-validation): builder suite and README commands on a no-.git copy, per interpreter. Usage: run_builder_m20.sh TREE OUTDIR PY...
T=$1; OUT=$2; shift 2; mkdir -p $OUT
for py in "$@"; do v=$($py -c 'import platform;print(platform.python_version())'); S=/tmp/m20-suite-$v; rm -rf $S; rsync -a --exclude .git $T/ $S/
 { echo "=== $v $(date '+%H:%M:%S %Z')"; cd $S
   for cmd in "examples/capabilities/G20/ui_oracle.py" "examples/capabilities/G20/ui_oracle.py --core examples/capabilities/G20/naive_core.js" "examples/capabilities/G20/ui_oracle.py --core examples/capabilities/G20/noop_core.js" "examples/capabilities/G20/ui_oracle.py --seed 2026 --scale 10"; do
     echo "\$ python3 $cmd"; $py ${=cmd} 2>&1 | tail -8; echo "[exit $pipestatus[1]]"; done
   echo "\$ unittest tests.test_g20_capability"; $py -m unittest tests.test_g20_capability 2>&1 | tail -4
   echo "\$ unittest discover (full suite)"; $py -m unittest discover -s tests -t . 2>&1 | tail -4
   git -C $S status >/dev/null 2>&1; echo "files changed by the run: $(cd $S && find . -newer $S/README.md -type f -not -path './.git*' 2>/dev/null | wc -l | tr -d ' ') (newer than README.md)"
 } > $OUT/builder-$v.txt 2>&1; rm -rf $S; done; echo BUILDER-DONE
