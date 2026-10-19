#!/bin/zsh
# M08 r2 runner (Grok self-validation): private copy of the candidate; suites, builder oracle and M08 oracle on four
# interpreters (run_all.sh), lock probes and the concurrency drills on 3.9.6 and 3.13.15. Teeth run separately.
N=$1; O=$N/oracle; C=$(mktemp -d /tmp/m08r2run-XXXXXX); rsync -a --exclude .git /tmp/m08r2-eval/ $C/
P9=/usr/bin/python3; P11=<UV>/python/cpython-3.11.16-macos-aarch64-none/bin/python3
P12=<PY312>; P13=<UV>/python/cpython-3.13.15-macos-aarch64-none/bin/python3
mkdir -p $N/results/race $N/results/lock
zsh $O/run_all.sh $O $N/results $C $P9 $P11 $P12 $P13 > $N/results/run_all.log 2>&1 &
for P in $P9 $P13; do V=$($P -c 'import sys;print(sys.version.split()[0])')
  $P $O/m08r2_lock.py $C $N/results/lock/lock-$V.json > $N/results/lock/lock-$V.txt 2>&1
  for s in m08_race_sweep m08_race_followup m08_race_rollback; do $P $O/$s.py $C $N/results/race/$s-$V.json > $N/results/race/$s-$V.txt 2>&1; done
done
wait
print -r -- "pycache in copy: $(find $C -name __pycache__ | wc -l | tr -d ' ')"; rm -rf $C
print -r -- "candidate status lines: $(git -C /tmp/m08r2-eval status --porcelain | wc -l | tr -d ' ')"; print -r -- RUN-DONE
