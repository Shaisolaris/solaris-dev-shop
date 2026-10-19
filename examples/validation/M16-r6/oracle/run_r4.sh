#!/bin/zsh
# M16 r4 runner (Grok self-validation). Usage: zsh run_r4.sh ORACLE_DIR OUT_DIR TREE LABEL PY...
# Per interpreter, on a copy of TREE (no .git): G16 tests, the non-G16 tests, the full suite; then the full
# m16_oracle, M16 r2/r3/r4 adversarial sets and the builder grounding_oracle against TREE's grounded_eval.py.
O=$1; R=$2; C=$3; L=$4; shift 4; export PYTHONDONTWRITEBYTECODE=1; T=employees/engineering/llm-agent-designer/grounded_eval.py
mkdir -p $R
for py in $@; do v=$($py -c 'import sys;print(sys.version.split()[0])'); f=$R/$L-$v.txt
  S=/tmp/m16r5-suite-$L-$v; rm -rf $S; rsync -a --exclude .git $C/ $S/; cd $S
  echo "=== $L $v $(date '+%F %T %Z')" > $f
  for pat in test_g16_capability.py 'test_[!g]*.py' 'test*.py'; do $py -m unittest discover -s tests -p "$pat" > $S.log 2>&1; echo "suite $pat: rc=$? $(grep -E '^(Ran|OK|FAILED)' $S.log | tr '\n' ' ')" >> $f; done
  echo "--- m16_oracle" >> $f; $py $O/m16_oracle.py -- $py $S/$T 2>&1 | tail -4 >> $f
  for a in m16r2_adversarial m16r3_adversarial m16r4_adversarial; do echo "--- $a" >> $f; $py $O/$a.py $py $S/$T > $S.adv 2>&1; grep -E "^\w+ (HOLDS|GAP)" $S.adv | awk '{print $1, $2}' | tr '\n' ';' >> $f; echo >> $f; grep -E "^HOLDS|holds [0-9]|HOLD [0-9]" $S.adv >> $f; done
  echo "--- builder grounding_oracle" >> $f; $py $S/examples/capabilities/G16/grounding_oracle.py --tool "$py $S/$T" 2>&1 | tail -2 >> $f
  cd /tmp; rm -rf $S $S.log $S.adv
done
echo R4-DONE
