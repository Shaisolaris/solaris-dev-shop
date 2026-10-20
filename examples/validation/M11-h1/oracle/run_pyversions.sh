#!/bin/bash
# run_pyversions.sh: M11 h1 probe on h1 (cand) and on accepted 13ba705 (acc), the G18 cross-checks as published (g18 = fd94c64)
# and with the G11 h1 incident_slo.py and doc overlaid (g18o), and the G11 oracle on h1. Run from a folder holding those four
# trees. Interpreters come from PY39 PY311 PY312 PY313 (3.9.6, 3.11.16, 3.12.14, 3.13.15 in this pass).
for P in "${PY39:-python3.9}" "${PY311:-python3.11}" "${PY312:-python3.12}" "${PY313:-python3.13}"; do
 v=$($P -V | cut -d' ' -f2); export PYTHONDONTWRITEBYTECODE=1
 $P out/oracle/m11h1_probe.py cand > out/results/probe-h1-$v.txt 2>&1; echo "probe h1 $v rc=$? $(tail -1 out/results/probe-h1-$v.txt)"
 $P out/oracle/m11h1_probe.py acc > out/results/probe-accepted-13ba705-$v.txt 2>&1; echo "probe 13ba705 $v rc=$? $(tail -1 out/results/probe-accepted-13ba705-$v.txt)"
 (cd g18 && $P examples/capabilities/G18/cross_checks.py) > out/results/g18-crosschecks-fd94c64-$v.txt 2>&1; echo "G18 x-checks as published $v rc=$? $(tail -1 out/results/g18-crosschecks-fd94c64-$v.txt)"
 (cd g18o && $P examples/capabilities/G18/cross_checks.py) > out/results/g18-crosschecks-with-g11h1-$v.txt 2>&1; echo "G18 x-checks with G11 h1 $v rc=$? $(tail -1 out/results/g18-crosschecks-with-g11h1-$v.txt)"
 (cd cand && $P examples/capabilities/G11/incident_oracle.py -- $P employees/infrastructure/site-reliability-engineer/incident_slo.py) > out/results/g11-oracle-h1-$v.txt 2>&1; echo "G11 oracle h1 $v rc=$? $(tail -1 out/results/g11-oracle-h1-$v.txt)"
done
