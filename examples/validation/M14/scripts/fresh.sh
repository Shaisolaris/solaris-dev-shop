#!/bin/zsh
# Fresh caller (Grok self-validation): env -i, new HOME, python3 shim, only the README commands, on a copy.
PYREAL=$1; C=$(mktemp -d /tmp/m14fr-XXXXXX); rsync -a --exclude .git /tmp/m14-eval/ $C/repo/; mkdir -p $C/home $C/bin; ln -s $PYREAL $C/bin/python3
cd $C/repo; T=employees/leadership/cfo/cash_revenue_reconcile.py; O=examples/capabilities/G14
for cmd in "python3 $T reconcile $O/fixtures/clean/package.json" "python3 $T reconcile $O/fixtures/september/package.json" "python3 $T reconcile $O/fixtures/september/package.json --json" "python3 $T reconcile $O/README.md" "python3 $T reconcile $O/fixtures/september/package.json --json --out r.json"; do
  out=$(env -i HOME=$C/home PATH=$C/bin:/usr/bin:/bin zsh -c "$cmd" 2>&1); rc=$?
  print -r -- "-- rc=$rc :: $cmd"; print -r -- "$out" | head -14
done
env -i HOME=$C/home PATH=$C/bin:/usr/bin:/bin python3 $T reconcile $O/fixtures/september/package.json --json | python3 -c '
import json,sys;d=json.load(sys.stdin)
for c,v in sorted(d["currencies"].items()): print(c, v["billed"], v["credit_notes"], v["recognized_revenue"], v["cash_received"], v["refunds_paid"], v["opening"]["ar_net"], v["closing"]["ar_net"], v["closing"]["deferred"], v["closing"]["unapplied"])'
print -r -- "new files in copy (besides r.json): $(cd $C/repo && find . -newer $C/home -type f | grep -v '^./r.json$' | wc -l | tr -d ' '), pycache: $(find $C/repo -name __pycache__ | wc -l | tr -d ' ')"
rm -rf $C
