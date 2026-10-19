#!/bin/zsh
# M39 fresh caller (Grok self-validation): every line of the G39 README "## Run" block, verbatim, under env -i with a new HOME,
# python3 = the given interpreter, STATE = a fresh empty temp folder (the README uses $STATE for --out), on a copy.
setopt null_glob
OUT=$1; SRC=/tmp/m39-eval; : > $OUT
for PY in /usr/bin/python3 <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  D=$(mktemp -d /tmp/m39fc-XXXXXX); mkdir -p $D/bin $D/home $D/state; ln -s $PY $D/bin/python3; rsync -a --exclude .git $SRC/ $D/c/
  awk '/^## Run/{f=1;next} f&&/^```/{if(g)exit; g=1;next} g' $D/c/examples/capabilities/G39/README.md > $D/run.txt
  (cd $D/c && find . -type f | sort | xargs shasum > $D/before.txt)
  print -r -- "== $($PY -c 'import sys;print(sys.version.split()[0])')" >> $OUT
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    o=$(cd $D/c && env -i PATH=$D/bin:/usr/bin:/bin HOME=$D/home LC_ALL=C TMPDIR=$D/home STATE=$D/state /bin/bash -c "$line" 2>&1); rc=$?
    print -r -- "$ $line" >> $OUT; print -r -- "  -> exit $rc; last line: $(print -r -- $o | tail -1 | cut -c1-160)" >> $OUT
  done < $D/run.txt
  (cd $D/c && find . -type f | sort | xargs shasum > $D/after.txt)
  print -r -- "-- --out files: $(cd $D/state && find . -type f | sort | tr '\n' ' '); pycache dirs in copy: $(find $D/c -name __pycache__ | wc -l | tr -d ' '); tree changed: $(diff -q $D/before.txt $D/after.txt >/dev/null && echo no || echo yes); HOME entries: $(cd $D/home && find . -mindepth 1 -maxdepth 3 | tr '\n' ' ')" >> $OUT
  rm -rf $D
done
