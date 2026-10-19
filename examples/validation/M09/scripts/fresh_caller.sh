#!/bin/zsh
# M09 fresh caller (Grok self-validation): the G09 README demo, verbatim, under env -i with a new HOME, on a private copy.
for PY in /usr/bin/python3 <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  F=$(mktemp -d /tmp/m09fr-XXXXXX); rsync -a --exclude .git /tmp/m09-eval/ $F/r/; mkdir $F/home; cd $F/r
  B=$(find . -type f -not -path './.git/*' -exec shasum -a 256 {} + | sort | shasum -a 256)
  T=employees/infrastructure/kubernetes-specialist/k8s_manifest_check.py
  E=(env -i HOME=$F/home PATH=/usr/bin:/bin LC_ALL=C)
  print -r -- "== $($PY -c 'import sys;print(sys.version.split()[0])')"
  $E $PY $T check examples/capabilities/G09/fixtures/clean > $F/o1 2>&1; print -r -- "clean rc=$? want 0 | $(tail -1 $F/o1)"
  $E $PY $T check examples/capabilities/G09/fixtures/broken > $F/o2 2>&1; print -r -- "broken rc=$? want 1"; cat $F/o2
  $E $PY $T check examples/capabilities/G09/fixtures/broken --json > $F/o3 2>&1; print -r -- "broken --json rc=$? want 1 | lines $($PY -c "import json;d=json.load(open('$F/o3'));print([(f['code'],f['line']) for f in d['findings'] if f['severity']=='error'])")"
  $E $PY $T check examples/capabilities/G09/README.md > $F/o4 2>&1; print -r -- "README rc=$? want 2 | $(cat $F/o4 | tr '\n' ' ')"
  $E $PY examples/capabilities/G09/k8s_oracle.py > $F/o5 2>&1; print -r -- "oracle rc=$? | $(tail -1 $F/o5)"
  $E $PY examples/capabilities/G09/k8s_oracle.py --tool examples/capabilities/G09/noop_check.py > $F/o6 2>&1; print -r -- "noop rc=$? | $(tail -1 $F/o6)"
  A=$(find . -type f -not -path './.git/*' -exec shasum -a 256 {} + | sort | shasum -a 256)
  print -r -- "tree unchanged: $([[ $B == $A ]] && echo yes || echo NO) | pycache: $(find . -name __pycache__ | wc -l | tr -d ' ') | home entries: $(ls -A $F/home | wc -l | tr -d ' ')"
  cd /tmp; rm -rf $F
done
