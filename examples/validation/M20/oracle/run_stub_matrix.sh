#!/bin/zsh
# Run the M20 prep oracle on every Grok-made stub (Grok self-validation; stub results certify no candidate).
cd ${0:A:h}/..
for s in noop naive textcheck reference reference-global; do
  echo "=== $s"; /usr/bin/python3 oracle/m20_oracle.py stubs/binding-$s.json raw/stub-$s --perf-reps 10 > raw/stub-$s.stdout.txt 2>&1
  echo "[exit $?]"; grep -E "^core " raw/stub-$s.stdout.txt
done
