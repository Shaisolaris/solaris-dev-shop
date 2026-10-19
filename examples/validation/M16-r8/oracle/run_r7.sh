#!/bin/zsh
# M16 r7 runner (Grok self-validation). Usage: zsh run_r7.sh ORACLE_DIR RESULTS TREE LABEL PY...
# run_r4.sh instruments (suites, m16_oracle, r2/r3/r4 adversarial, builder grounding_oracle), then the r6 wide table,
# r6 and r5 probes, and the new r7 greeting table and greeting probes, against TREE's grounded_eval.py.
O=$1; R=$2; C=$3; L=$4; shift 4; export PYTHONDONTWRITEBYTECODE=1; T=$C/employees/engineering/llm-agent-designer/grounded_eval.py
zsh $O/run_r4.sh $O $R/instruments $C $L $@ > /dev/null
mkdir -p $R/table $R/probes $R/greetings $R/greeting-probes
for py in $@; do v=$($py -c 'import sys;print(sys.version.split()[0])')
  $py $O/m16r6_table.py ${T:h} $R/table/$L-$v.json > $R/table/$L-$v.txt 2>&1
  $py $O/m16r6_probes.py $py $T > $R/probes/$L-$v.txt 2>&1
  $py $O/m16r5_probes.py $py $T > $R/probes/r5set-$L-$v.txt 2>&1
  $py $O/m16r7_greetings.py ${T:h} $R/greetings/$L-$v.json > $R/greetings/$L-$v.txt 2>&1
  $py $O/m16r7_greeting_probes.py $py $T > $R/greeting-probes/$L-$v.txt 2>&1
done
echo R7-DONE $L
