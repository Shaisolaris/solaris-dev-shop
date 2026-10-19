#!/bin/zsh
# M25 fresh caller (Grok self-validation). env -i, new HOME, python3 shim, socket-blocking sitecustomize.
# Commands transcribed by hand from device-event-protocol.md "## Commands" (the doc's continuation lines are
# joined); C and E are the doc's own out/commands.jsonl and out/events.jsonl. cwd = the iot-engineer folder.
# Pass 1 runs the doc verbatim on a fresh folder; pass 2 adds the one deviation `mkdir out`.
# Usage: m25_fresh_caller.sh PYTHON TREE OUT
PY=$1; TREE=$2; OUT=$3; F=$(mktemp -d /tmp/m25-fc-XXXXXX); CWD=$TREE/employees/engineering/iot-engineer
mkdir -p $F/home $F/shim $F/guard; ln -s $PY $F/shim/python3
cat > $F/guard/sitecustomize.py <<'PY'
import socket
def _blocked(*a, **k):
    raise OSError("offline guard: network blocked in fresh caller")
socket.socket.connect = _blocked
socket.create_connection = _blocked
PY
CMDS=("python3 device_protocol.py simulate --devices 12 --steps 300 --seed 7 --faults drop=0.2,dup=0.2,reorder=0.3,disconnect=0.05,reboot=0.02 --record out/"
      "python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --json"
      "python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --state st.json --crash-after 500"
      "python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --state st.json")
run() {
  print -r -- "--- $1"
  o=$(cd $CWD && env -i HOME=$F/home PATH=$F/shim:/usr/bin:/bin PYTHONPATH=$F/guard PYTHONDONTWRITEBYTECODE=1 zsh -c "$1" 2>&1); rc=$?
  print -r -- "rc=$rc"
  print -r -- "$o" | /usr/bin/python3 -c '
import json,sys
t=sys.stdin.read()
try:
    d=json.loads(t); print({k:d[k] for k in ("status","effects_claimed","commands_issued","anomalies_found","resumed_from_line") if k in d})
except ValueError:
    print("\n".join(t.strip().splitlines()[-3:])[:400])'
}
{
print -r -- "fresh caller (Grok self-validation): env -i, HOME=\$FC/home, PATH=\$FC/shim:/usr/bin:/bin (python3 -> $($PY -V 2>&1)), offline guard; cwd=<tree>/employees/engineering/iot-engineer"
rm -rf $CWD/out $CWD/st.json
print -r -- "== pass 1: doc verbatim on a folder without out/"
for c in $CMDS; do run "$c"; done
rm -rf $CWD/out $CWD/st.json
print -r -- "== pass 2: deviation 'mkdir out' first"
mkdir $CWD/out
for c in $CMDS; do run "$c"; done
run "python3 -c 'import socket; socket.create_connection((\"example.com\", 80))'"
J1=$(cd $CWD && env -i HOME=$F/home PATH=$F/shim:/usr/bin:/bin PYTHONPATH=$F/guard python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --json | /usr/bin/python3 -c 'import json,sys;d=json.load(sys.stdin);d.pop("resumed_from_line",None);print(json.dumps(d,sort_keys=True))' | shasum -a 256 | cut -c1-16)
rm -f $CWD/st.json
(cd $CWD && env -i HOME=$F/home PATH=$F/shim:/usr/bin:/bin PYTHONPATH=$F/guard python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --state st.json --crash-after 500 >/dev/null 2>&1)
J2=$(cd $CWD && env -i HOME=$F/home PATH=$F/shim:/usr/bin:/bin PYTHONPATH=$F/guard python3 device_protocol.py ingest --commands out/commands.jsonl --events out/events.jsonl --state st.json --json | /usr/bin/python3 -c 'import json,sys;d=json.load(sys.stdin);d.pop("resumed_from_line",None);print(json.dumps(d,sort_keys=True))' | shasum -a 256 | cut -c1-16)
print -r -- "unbroken report $J1 vs crash+resume report $J2: $([ $J1 = $J2 ] && echo identical || echo DIFFERENT)"
} > $OUT
rm -rf $CWD/out $CWD/st.json $F
