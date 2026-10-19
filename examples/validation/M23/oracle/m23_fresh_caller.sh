#!/bin/zsh
# M23 prep fresh caller (Grok self-validation). Copies the candidate tree without .git into a new temp dir,
# runs env -i with a new HOME and a PATH shim mapping python3 to PYTHON, a sitecustomize offline guard that
# refuses non-loopback sockets for Python, and only the commands in COMMANDS_FILE. COMMANDS_FILE is written
# by hand from the candidate's documentation before the run, one command per line, with "# expect:" lines
# holding the hand-written expectation. Then the M23 oracle runs against BINDING (path relative to the tree copy); its bundles are unseen by the candidate.
# Usage: m23_fresh_caller.sh PYTHON CANDIDATE_TREE COMMANDS_FILE BINDING_REL OUT_DIR
set -u
P=$1; C=$2; CMDS=$3; BREL=$4; OUT=$5
O=${0:A:h}
F=$(mktemp -d /tmp/m23prep-fresh-XXXXXX)
mkdir -p $F/home $F/bin $F/guard $OUT
rsync -a --exclude .git $C/ $F/repo/
ln -s $P $F/bin/python3
cat > $F/guard/sitecustomize.py <<'PY'
import socket
_orig = socket.socket.connect
def _guard(self, addr):
    host = addr[0] if isinstance(addr, tuple) else str(addr)
    if host not in ("127.0.0.1", "::1", "localhost") and not str(host).startswith("/"):
        raise OSError("offline guard: non-loopback connect refused: %r" % (addr,))
    return _orig(self, addr)
socket.socket.connect = _guard
PY
cp $CMDS $F/commands.txt
cat > $F/caller.sh <<'IN'
set -u
cd "$HOME/../repo"
echo "python3 = $(python3 -c 'import sys; print(sys.version.split()[0])'); env vars: $(env | wc -l | tr -d ' ')"
while IFS= read -r line; do
  case "$line" in
    ""|"# expect:"*) [ -n "$line" ] && echo "    $line"; continue;;
    "#"*) echo "$line"; continue;;
  esac
  echo "\$ $line"; eval "$line"; echo "[exit $?]"
done < ../commands.txt
IN
env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin PYTHONPATH=$F/guard zsh $F/caller.sh > $OUT/fresh-commands.txt 2>&1
echo "fresh commands transcript: $OUT/fresh-commands.txt"
env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin PYTHONPATH=$F/guard python3 $O/m23_oracle.py $F/repo/$BREL $OUT/oracle > $OUT/oracle-stdout.txt 2>&1
echo "[oracle exit $?]" >> $OUT/oracle-stdout.txt
tail -3 $OUT/oracle-stdout.txt
rm -rf $F
