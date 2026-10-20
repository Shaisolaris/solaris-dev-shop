#!/bin/bash
# suite.sh WT OUT : unittest discover on 4 Pythons, each in a fresh clone of WT HEAD. G20_CHROME is removed, so no test starts a browser.
WT=$1; OUT=$2; . <D>/grok-output/G39-r5/scripts/pys.sh; SHA=$(git -C $WT rev-parse HEAD); mkdir -p $OUT
one() { tag=$1; P=$2; d=$OUT/clone-$tag; rm -rf $d; git clone -q $WT $d && git -c advice.detachedHead=false -C $d checkout -q --detach $SHA
  (cd $d && env -u G20_CHROME PYTHONDONTWRITEBYTECODE=1 $P -m unittest discover -s tests > $OUT/suite-$tag.txt 2>&1); echo "rc=$? $($P -V) at $SHA" >> $OUT/suite-$tag.txt; rm -rf $d; }
one py39 $P39 & one py311 $P311 & one py312 $P312 & one py313 $P313 &
# browser watchdog: a Chrome started from these clones (g20-chrome- profile) is recorded and killed by pid (none expected)
while jobs %1 >/dev/null 2>&1 || jobs %2 >/dev/null 2>&1 || jobs %3 >/dev/null 2>&1 || jobs %4 >/dev/null 2>&1; do
  # only a Chrome using a g20-chrome- profile can come from these clones; anything else (the owner's apps) is never touched
  ps -axo pid,command | grep -E "user-data-dir=[^ ]*g20-chrome-" | grep -v grep | while read pid rest; do echo "BROWSER SEEN pid $pid $rest" >> $OUT/browser-watch.txt; kill $pid; done
  sleep 1; [ -z "$(jobs -r)" ] && break; done; wait
echo "browser processes seen during the run: $(cat $OUT/browser-watch.txt 2>/dev/null | wc -l | tr -d ' ')" > $OUT/browser-watch-summary.txt
for t in py39 py311 py312 py313; do echo "$t: $(grep -E '^(OK|FAILED|Ran)' $OUT/suite-$t.txt | tr '\n' ' ') $(tail -1 $OUT/suite-$t.txt)"; done | tee $OUT/matrix.log
cat $OUT/browser-watch-summary.txt
