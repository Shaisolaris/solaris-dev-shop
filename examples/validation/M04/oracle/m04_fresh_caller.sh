#!/bin/zsh
# M04 fresh caller (Grok self-validation): env -i, new HOME, python3 shim, offline guard, only the README "Try it" commands.
# The README's /tmp/g04-demo is placed under the fresh folder instead (disclosed). Usage: m04_fresh_caller.sh PYTHON CANDIDATE_TREE
PY=$1; C=$2; F=$(mktemp -d /tmp/m04-fresh-XXXXXX); mkdir -p $F/bin $F/home $F/guard
printf '#!/bin/sh\nexec %s "$@"\n' $PY > $F/bin/python3; chmod +x $F/bin/python3
printf 'import socket\ndef _no(*a, **k): raise OSError("offline guard: network disabled")\nsocket.socket.connect = _no\nsocket.create_connection = _no\n' > $F/guard/sitecustomize.py
env -i PATH=$F/bin:/usr/bin:/bin HOME=$F/home PYTHONPATH=$F/guard PYTHONDONTWRITEBYTECODE=1 C=$C F=$F /bin/zsh -f -c '
echo "python3 = $(python3 -c "import sys;print(sys.version.split()[0])"); env vars: $(env | wc -l | tr -d " ")"
cp -R $C/examples/capabilities/G04/fixtures $F/g04-demo && cd $F/g04-demo
H=$C/employees/infrastructure/fleet-dispatcher/handoff.py
for cmd in "run order.json --worker ana --fail-at deliver" "run order.json --worker ben" "status order.json"; do echo "\$ python3 \$H $cmd"; python3 $H ${=cmd} | sed "s#$F#FRESH#g"; echo "[exit $pipestatus[1]]"; done
echo "\$ wc -l outbox/ledger.jsonl"; echo "$(wc -l < outbox/ledger.jsonl | tr -d " ")"
for cmd in "run order-rev2.json --worker cy" "run order.json --worker ana"; do echo "\$ python3 \$H $cmd"; python3 $H ${=cmd} 2>&1 | sed "s#$F#FRESH#g"; echo "[exit $pipestatus[1]]"; done
echo "ledger lines now: $(wc -l < outbox/ledger.jsonl | tr -d " ")"
'
echo "pycache in candidate: $(find $C -name __pycache__ | wc -l | tr -d ' ')"; rm -rf $F
