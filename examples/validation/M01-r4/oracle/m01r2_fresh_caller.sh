#!/bin/zsh
# M01 r2 fresh caller (Grok self-validation). env -i, new HOME, python3 shim, socket-blocking sitecustomize.
# Commands transcribed by hand from ASSURANCE.md "## Commands"; packet.json and the suite dir are absolute paths.
# Usage: m01r2_fresh_caller.sh PYTHON TREE OUT
PY=$1; TREE=$2; OUT=$3; F=$(mktemp -d /tmp/m01r2-fc-XXXXXX)
mkdir -p $F/home $F/shim $F/guard $F/fx $F/fx-y01
ln -s $PY $F/shim/python3
cat > $F/guard/sitecustomize.py <<'PY'
import socket
def _blocked(*a, **k):
    raise OSError("offline guard: network blocked in fresh caller")
socket.socket.connect = _blocked
socket.create_connection = _blocked
PY
MISS='{"risk_level": "elevated", "dimensions": ["security"], "completed_gates": [], "evidence": {}}'
FINDING='{"finding_id": "f-9", "defect_kind": "security", "severity": "S1", "title": "IDOR", "evidence": ["probe: other tenant record returned"], "accountable_role": "security-auditor", "reporter_role": "qa-engineer", "status": "open", "verifier_role": "code-reviewer"}'
print -r -- "{\"fixture_kind\": \"packet\", \"packet\": $MISS, \"expectations\": {\"outcome\": \"fail_gate\", \"gate_codes\": [\"MISSING_SPECIALIST_GATE\"]}}" > $F/fx/packet.json
print -r -- "{\"fixture-kind\": \"closure\", \"finding\": $FINDING, \"closer_role\": \"security-auditor\", \"expect_blocked\": false}" > $F/fx/x01-misspelled-kind.json
cp $F/fx/packet.json $F/fx-y01/packet.json
print -r -- '{"fixture_type": "legal", "text": "I am your attorney; file this lawsuit now."}' > $F/fx-y01/y01-synonym-kind.json
E=employees/quality-security/assurance/quality_os.py
{
print -r -- "fresh caller (Grok self-validation): env -i, HOME=$F/home, PATH=$F/shim:/usr/bin:/bin (python3 -> $($PY -V 2>&1)), offline guard via PYTHONPATH sitecustomize; cwd=$TREE"
for c in "python3 $E self-test" "python3 $E run $F/fx/packet.json" "python3 $E suite $F/fx" "python3 $E suite $F/fx-y01" "python3 $E audit" "python3 $E route security" "python3 -m unittest discover -s tests -v" "python3 -c 'import socket; socket.create_connection((\"example.com\", 80))'"; do
  print -r -- "--- $c"
  o=$(cd $TREE && env -i HOME=$F/home PATH=$F/shim:/usr/bin:/bin PYTHONPATH=$F/guard PYTHONDONTWRITEBYTECODE=1 zsh -c "$c" 2>&1); rc=$?
  print -r -- "rc=$rc"
  print -r -- "$o" | python3 -c '
import json,sys
t=sys.stdin.read()
try:
    d=json.loads(t); print({k:d[k] for k in ("ok","gate_codes","total","passed","failed") if k in d})
except ValueError:
    print(" ".join(t.split()[-4:]))' 2>/dev/null
done
} > $OUT
rm -rf $F
