#!/bin/zsh
# M10 r2 fresh caller: env -i, a new HOME, a python3 shim, the M10 offline guard, and only the three
# commands in offline-trace-diagnosis.md, run in a /tmp copy of the candidate tree.
# Usage: zsh m10r2_fresh_caller.sh PYTHON CANDIDATE_TREE M10_ORACLE_DIR
PY=$1; C=$2; O=$3; F=/tmp/m10r2-fc
rm -rf $F; mkdir -p $F/home $F/bin $F/tree
rsync -a --exclude .git $C/ $F/tree/
printf '#!/bin/sh\nexec %s "$@"\n' "$PY" > $F/bin/python3; chmod +x $F/bin/python3
cp $F/tree/examples/capabilities/G10/fixtures/03-tls-name-mismatch.json $F/tree/trace.json 2>/dev/null || cp "$(ls $F/tree/examples/capabilities/G10/fixtures/*.json | head -1)" $F/tree/trace.json
mkdir -p $F/tree/traces; cp $F/tree/examples/capabilities/G10/fixtures/*.json $F/tree/traces/
(cd $F/tree && find . -type f | sort) > $F/before.txt
run() { echo "\$ $1"; env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin PYTHONPATH=$O/inject M10_NET_LOG=$F/net.log PYTHONDONTWRITEBYTECODE=1 \
  /bin/bash -c "cd $F/tree && T=employees/infrastructure/network-engineer/netdiag.py && $1"; echo "[exit $?]"; }
echo "# m10r2 fresh caller $(date '+%F %T %Z'); python3 shim -> $($PY -c 'import platform;print(platform.python_version())'); offline guard on (M10_NET_LOG); trace.json = fixture $(ls $F/tree/examples/capabilities/G10/fixtures | grep -c json) fixtures in traces/"
run 'python3 $T diagnose examples/capabilities/G10/fixtures/06-tls-expired.json'
run 'python3 $T diagnose trace.json --json --out report.json'
echo "report.json: $( [ -s $F/tree/report.json ] && $PY -c 'import json,sys;j=json.load(open(sys.argv[1]));print("schema",j["schema"],"verdict",j["verdict"],"layer",j["layer"],[f["code"] for f in j["findings"]])' $F/tree/report.json || echo missing)"
run 'python3 $T batch traces/ --workers 4'
(cd $F/tree && find . -type f | sort) > $F/after.txt
echo "network attempts logged: $( [ -f $F/net.log ] && wc -l < $F/net.log | tr -d ' ' || echo 0)"
echo "stray files: $(comm -13 $F/before.txt $F/after.txt | grep -v '^./report.json$' | tr '\n' ' ')"
echo "HOME after: $(find $F/home -mindepth 1 | wc -l | tr -d ' ') entries"
rm -rf $F
