#!/usr/bin/env bash
# Solaris Dev Shop one-command install (0.53).
# Verifies the tree, runs the control-plane self-test, and links the
# `solaris-intake` command into ~/.local/bin.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

echo "== Solaris Dev Shop 0.53 =="
echo "-- checking tree"
for f in control-plane/meta_control_plane.py control-plane/roster.json control-plane/policy.json chief-of-staff/SKILL.md; do
  [ -f "$f" ] || { echo "missing: $f"; exit 1; }
done
count=$(find employees -maxdepth 3 -name SKILL.md | wc -l | tr -d ' ')
echo "   employee skills: $count"

echo "-- control-plane self-test"
python3 control-plane/meta_control_plane.py self-test

echo "-- routing probes"
python3 tests/test_router.py 2>&1 | tail -3

echo "-- installing solaris-intake"
BIN_DIR="$HOME/.local/bin"
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/solaris-intake" <<EOF
#!/usr/bin/env bash
exec python3 "$ROOT/control-plane/meta_control_plane.py" "\$@"
EOF
chmod +x "$BIN_DIR/solaris-intake"

echo ""
echo "Done. Try:"
echo "  solaris-intake intake \"Write a test plan for the client portal login regression\""
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "  (add $BIN_DIR to your PATH to use solaris-intake anywhere)" ;;
esac
