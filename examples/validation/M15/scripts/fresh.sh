#!/bin/zsh
# Fresh caller (Grok self-validation): env -i, new HOME, python3 shim, only documented commands, on a copy.
PYREAL=$1; C=$(mktemp -d /tmp/m15fr-XXXXXX); rsync -a --exclude .git /tmp/m15-eval/ $C/repo/; mkdir -p $C/home $C/bin; ln -s $PYREAL $C/bin/python3
cd $C/repo; T=employees/data/data-scientist/experiment_readout.py; O=examples/capabilities/G15
for f in clean-aa retention-lift sample-ratio-mismatch; do
  out=$(env -i HOME=$C/home PATH=$C/bin:/usr/bin:/bin python3 $T analyse $O/fixtures/$f/package.json --json 2>&1); rc=$?
  print -r -- "-- rc=$rc $f :: $(print -r -- "$out" | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["outcome"],{a:(v["units"],v["converted"]) for a,v in d["arms"].items()},d["claims_allowed"])')"
done
out=$(env -i HOME=$C/home PATH=$C/bin:/usr/bin:/bin python3 $T analyse $O/README.md 2>&1); print -r -- "-- rc=$? README.md :: $out" | head -2
env -i HOME=$C/home PATH=$C/bin:/usr/bin:/bin python3 $T analyse $O/fixtures/clean-aa/package.json --out r.json >/dev/null; print -r -- "-- rc=$? --out written: $(test -s r.json && echo yes)"
print -r -- "new files in copy (besides r.json): $(cd $C/repo && find . -newer $C/home -type f | grep -v '^./r.json$' | wc -l | tr -d ' '), pycache: $(find $C/repo -name __pycache__ | wc -l | tr -d ' ')"
rm -rf $C
