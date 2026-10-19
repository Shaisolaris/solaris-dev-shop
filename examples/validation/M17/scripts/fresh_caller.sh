#!/bin/zsh
# M17 fresh caller (Grok self-validation): the G17 README demo, verbatim, under env -i with a new HOME, on a private copy,
# plus the README's worked figures and the unreconciled-books claim checked against the JSON report.
for PY in /usr/bin/python3 <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  F=$(mktemp -d /tmp/m17fr-XXXXXX); rsync -a --exclude .git /tmp/m17-eval/ $F/r/; mkdir $F/home; cd $F/r
  B=$(find . -type f -exec shasum -a 256 {} + | sort | shasum -a 256)
  T=employees/leadership/coo/resource_decision.py; X=examples/capabilities/G17
  E=(env -i HOME=$F/home PATH=/usr/bin:/bin LC_ALL=C)
  print -r -- "== $($PY -c 'import sys;print(sys.version.split()[0])')"
  $E $PY $T evaluate $X/fixtures/studio.json > $F/o1 2>&1; print -r -- "evaluate rc=$? want 0"; cat $F/o1
  $E $PY $T evaluate $X/fixtures/studio.json --json > $F/o2 2>&1; print -r -- "evaluate --json rc=$? want 0"
  $PY - $F/o2 <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1])); o = {x["id"]: x for x in d["options"]}
dn = lambda i: o[i]["cases"]["downside"]
print("status", d["status"], "feasible_in_downside", d["feasible_in_downside"])
print("as-is finish", dn("as-is").get("finish_weeks"), "closing", dn("as-is")["cash"]["closing"], "lowest", dn("as-is")["cash"]["lowest"])
for i in o: print(i, "feasible", dn(i)["feasible"], "breach", dn(i)["cash"].get("buffer_breach"), "short", [(m.get("binding"), m.get("capacity_short_hours")) for m in dn(i)["milestones"]])
PYEOF
  $E $PY $X/decision_oracle.py > $F/o3 2>&1; print -r -- "oracle rc=$? | $(tail -1 $F/o3)"
  $E $PY $X/decision_oracle.py --tool $X/naive_decision.py > $F/o4 2>&1; print -r -- "naive rc=$? | $(tail -1 $F/o4)"
  $E $PY $X/decision_oracle.py --tool $X/noop_decision.py > $F/o5 2>&1; print -r -- "noop rc=$? | $(tail -1 $F/o5)"
  mkdir $F/u; sed 's#books-sept#books-unreconciled#g' $X/fixtures/studio.json > $F/u/studio-unrec.json; cp -R $X/fixtures/books-unreconciled $F/u/ 2>/dev/null
  $E $PY $T evaluate $F/u/studio-unrec.json --json > $F/o6 2>&1; print -r -- "unreconciled books rc=$? want 1 | $($PY -c "import json;d=json.load(open('$F/o6'));print(d['status'])" 2>&1 | tail -1)"
  A=$(find . -type f -exec shasum -a 256 {} + | sort | shasum -a 256)
  print -r -- "tree unchanged: $([[ $B == $A ]] && echo yes || echo NO) | pycache: $(find . -name __pycache__ | wc -l | tr -d ' ') | home: $(find $F/home -mindepth 1 -maxdepth 3 | tr '\n' ' ')"
  cd /tmp; rm -rf $F
done
