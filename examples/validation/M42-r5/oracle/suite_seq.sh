#!/bin/bash
# suite_seq.sh WT OUT : like /tmp/b1603/suite.sh but one Python at a time (avoids parallel pip build timeouts in G40 wheel-smoke).
WT=$1; OUT=$2; . /tmp/g18/scripts/pys.sh; SHA=$(git -C $WT rev-parse HEAD); mkdir -p $OUT
one() { tag=$1; P=$2; d=$OUT/clone-$tag; rm -rf $d; git clone -q $WT $d && git -c advice.detachedHead=false -C $d checkout -q --detach $SHA
  s=$(date +%s); (cd $d && env -u G20_CHROME PYTHONDONTWRITEBYTECODE=1 $P -m unittest discover -s tests > $OUT/suite-$tag.txt 2>&1); echo "rc=$? $($P -V) at $SHA, $(( $(date +%s)-s ))s, started $(date -r $s '+%H:%M:%S %Z')" >> $OUT/suite-$tag.txt; rm -rf $d; }
( while :; do ps -axo pid,command | grep -E "user-data-dir=[^ ]*g20-chrome-" | grep -v grep | while read pid rest; do echo "BROWSER SEEN pid $pid $rest" >> $OUT/browser-watch.txt; kill $pid; done; sleep 2; done ) & W=$!
one py39 $P39; one py311 $P311; one py312 $P312; one py313 $P313
kill $W 2>/dev/null; wait $W 2>/dev/null
echo "browser processes seen during the run: $(cat $OUT/browser-watch.txt 2>/dev/null | wc -l | tr -d ' ')" > $OUT/browser-watch-summary.txt
for t in py39 py311 py312 py313; do echo "$t: $(grep -E '^(OK|FAILED|Ran)' $OUT/suite-$t.txt | tr '\n' ' ') $(tail -1 $OUT/suite-$t.txt)"; done | tee $OUT/matrix.log
cat $OUT/browser-watch-summary.txt
