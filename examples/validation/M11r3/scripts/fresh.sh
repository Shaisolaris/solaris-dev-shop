#!/bin/zsh
# Fresh caller (Grok self-validation): env -i, new HOME, python3 shim, only the README commands, on a copy.
PYREAL=$1; C=$(mktemp -d /tmp/m11r3fr-XXXXXX); rsync -a --exclude .git /tmp/m11r3-eval/ $C/repo/; mkdir -p $C/home $C/bin; ln -s $PYREAL $C/bin/python3
cd $C/repo; T=employees/infrastructure/site-reliability-engineer/incident_slo.py; O=examples/capabilities/G11
for cmd in "python3 $T report $O/fixtures/02-deploy-regression.json" "python3 $T report $O/fixtures/03-dns-fault-during-impact.json" "python3 $T report $O/fixtures/05-gap-after-change.json --json" "python3 $T report $O/README.md" "python3 $T report $O/fixtures/02-deploy-regression.json --json --out r.json"; do
  out=$(env -i HOME=$C/home PATH=$C/bin:/usr/bin:/bin zsh -c "$cmd" 2>&1); rc=$?
  print -r -- "-- rc=$rc :: $cmd"; print -r -- "$out" | grep -E 'decision|status|availability|invalid|burn' | head -6
done
for f in $O/fixtures/0*.json; do env -i HOME=$C/home PATH=$C/bin:/usr/bin:/bin python3 $T report $f --json | python3 -c 'import json,sys;d=json.load(sys.stdin);print(sys.argv[1].split("/")[-1],d["slo"]["status"],d["slo"]["availability"],d["slo"]["burn_rate"],d["slo"]["coverage"],d["decision"]["decision"])' $f; done
print -r -- "new files in copy: $(cd $C/repo && find . -newer $C/home -type f | grep -v '^./r.json$' | wc -l | tr -d ' '), pycache: $(find $C/repo -name __pycache__ | wc -l | tr -d ' ')"
rm -rf $C
