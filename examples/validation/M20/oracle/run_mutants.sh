#!/bin/zsh
# Run the M20 oracle on each reference mutant listed in the args (or all). Grok self-validation.
cd ${0:A:h}/..
names=("$@"); [ ${#names} -eq 0 ] && names=($(/usr/bin/python3 -c "import json;print(' '.join(m['mutant'] for m in json.load(open('stubs/mutants/plan.json'))))"))
for m in $names; do
  /usr/bin/python3 oracle/m20_oracle.py stubs/mutants/binding-$m.json raw/mut-$m --perf-reps 1 > raw/mut-$m.stdout.txt 2>&1
  echo "$m [exit $?] $(grep -E '^core ' raw/mut-$m.stdout.txt)"
done
