#!/bin/zsh
# M34 fresh caller (Grok self-validation): a no-.git copy, env -i, a new HOME, a python3 shim, a sitecustomize offline guard,
# and only the README Commands block. Disclosed change: the README's /tmp/before.json and /tmp/g34-fixtures are replaced by
# paths under the fresh folder, so nothing outside it is written. v2: the T=/F= line is evaluated in the caller shell (v1 lost it in a pipeline subshell, a harness bug). Usage: m34_fresh_caller.sh PYTHON TREE OUT
P=$1; C=$2; OUT=$3; F=$(mktemp -d /tmp/m34-fresh-XXXXXX); mkdir -p $F/home $F/bin $F/guard $F/tmp
rsync -a --exclude .git $C/ $F/repo/; ln -s $P $F/bin/python3
cat > $F/guard/sitecustomize.py <<'PY'
import socket
_o = socket.socket.connect
def _g(self, a):
    h = a[0] if isinstance(a, tuple) else str(a)
    if h not in ("127.0.0.1", "::1", "localhost") and not str(h).startswith("/"):
        raise OSError("offline guard: non-loopback connect refused: %r" % (a,))
    return _o(self, a)
socket.socket.connect = _g
PY
sed -n '/^T=employees/,/make_fixtures.py/p' $C/examples/capabilities/G34/README.md | sed "s#/tmp/#$F/tmp/#g" > $F/cmds.txt
cat > $F/caller.sh <<'IN'
cd "$HOME/../repo"; echo "python3 = $(python3 -c 'import sys;print(sys.version.split()[0])')"
while IFS= read -r line; do echo "\$ $line"; case "$line" in T=*) eval "$line"; echo "[set]"; continue;; esac; eval "${line%%#*}" 2>&1 | tail -4; echo "[exit $pipestatus[1]]  expected: ${line#*#}"; done < ../cmds.txt
IN
env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin PYTHONPATH=$F/guard zsh $F/caller.sh > $OUT 2>&1
echo "regenerated fixtures identical to committed: $(diff -r $F/tmp/g34-fixtures $C/examples/capabilities/G34/fixtures >/dev/null 2>&1 && echo yes || echo no)" >> $OUT
echo "pycache left in tree: $(find $F/repo -name __pycache__ | wc -l | tr -d ' ')" >> $OUT
rm -rf $F
