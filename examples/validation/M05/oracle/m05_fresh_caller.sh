#!/bin/zsh
# M05 fresh caller (Grok self-validation): env -i, new HOME, python3 shim, offline guard; only the README and ASSURANCE.md
# commands, run from a no-.git copy of the candidate. Usage: m05_fresh_caller.sh PYTHON CANDIDATE_TREE
PY=$1; C=$2; F=$(mktemp -d /tmp/m05-fresh-XXXXXX); mkdir -p $F/bin $F/home $F/guard; rsync -a --exclude .git $C/ $F/repo/
printf '#!/bin/sh\nexec %s "$@"\n' $PY > $F/bin/python3; chmod +x $F/bin/python3
printf 'import socket\ndef _no(*a, **k): raise OSError("offline guard: network disabled")\nsocket.socket.connect = _no\nsocket.create_connection = _no\n' > $F/guard/sitecustomize.py
env -i PATH=$F/bin:/usr/bin:/bin HOME=$F/home PYTHONPATH=$F/guard PYTHONDONTWRITEBYTECODE=1 F=$F /bin/zsh -f -c '
cd $F/repo; echo "python3 = $(python3 -c "import sys;print(sys.version.split()[0])")"; Q=employees/quality-security/assurance/quality_os.py
for c in "digest examples/capabilities/G05/fixtures/project-r2 src ui --revision 9b3e7d1c5a2f8e0b6d4c1a9f7e3b5d2c8a0f6e1b" "self-test" "route security"; do echo "\$ python3 \$Q $c"; python3 $Q ${=c} 2>&1 | head -12; echo "[exit $pipestatus[1]]"; done
for t in "" "--tool examples/capabilities/G05/naive_engine.py" "--tool examples/capabilities/G05/noop_engine.py"; do echo "\$ python3 examples/capabilities/G05/binding_oracle.py $t"; python3 examples/capabilities/G05/binding_oracle.py ${=t} 2>&1 | grep -E "checks passed"; echo "[exit $pipestatus[1]]"; done
echo "pycache: $(find . -name __pycache__ | wc -l | tr -d " ")"'
rm -rf $F
