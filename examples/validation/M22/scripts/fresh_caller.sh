#!/bin/zsh
# M22 fresh caller (Grok self-validation): the G22 README demo, verbatim, under env -i with a new HOME and python3 = the given interpreter, on a copy.
setopt null_glob
OUT=$1; SRC=/tmp/m22-eval; : > $OUT
for PY in /usr/bin/python3 <UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3; do
  D=$(mktemp -d /tmp/m22fc-XXXXXX); mkdir -p $D/bin $D/home; ln -s $PY $D/bin/python3; rsync -a --exclude .git $SRC/ $D/c/
  awk '/^## Demo/{f=1} f&&/^```bash/{g=1;next} g&&/^```/{exit} g' $D/c/examples/capabilities/G22/README.md > $D/demo.sh
  (cd $D/c && find . -type f | sort | xargs shasum > $D/before.txt)
  (cd $D/c && env -i PATH=$D/bin:/usr/bin:/bin HOME=$D/home LC_ALL=C TMPDIR=$D/home /bin/bash $D/demo.sh > $D/out.txt 2>&1); rc=$?
  (cd $D/c && find . -type f | sort | xargs shasum > $D/after.txt)
  print -r -- "== $($PY -c 'import sys;print(sys.version.split()[0])') demo exit $rc" >> $OUT; cat $D/out.txt >> $OUT
  print -r -- "-- pycache dirs in copy: $(find $D/c -name __pycache__ | wc -l | tr -d ' '); tree changed: $(diff -q $D/before.txt $D/after.txt >/dev/null && echo no || echo yes); HOME entries: $(cd $D/home && find . -mindepth 1 -maxdepth 3 | grep -v '^./tmp' | tr '\n' ' ')" >> $OUT
  rm -rf $D
done
