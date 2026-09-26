#!/usr/bin/env bash
# Solaris Dev Shop one-command install (0.53).
#
# From a checkout:   ./install.sh
# From anywhere:     curl -fsSL https://raw.githubusercontent.com/Shaisolaris/solaris-dev-shop/main/install.sh | bash
# Uninstall:         ./install.sh --uninstall   (or: curl ... | bash -s -- --uninstall)
#
# Verifies the tree, runs the control-plane self-test, and links the
# `solaris-intake` command into ~/.local/bin.
set -euo pipefail

REPO="https://github.com/Shaisolaris/solaris-dev-shop.git"
TARGET="$HOME/.solaris-dev-shop"

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$HOME/.local/bin/solaris-intake"
  if [ -d "$TARGET" ]; then
    rm -rf "$TARGET"
    echo "Removed $TARGET and the solaris-intake shim."
  else
    echo "Removed the solaris-intake shim. (No $TARGET checkout found.)"
  fi
  exit 0
fi

# When piped via curl there is no checkout; clone one first.
if [ ! -f "control-plane/meta_control_plane.py" ]; then
  if [ -d "$TARGET" ]; then
    echo "-- updating existing checkout at $TARGET"
    git -C "$TARGET" pull --ff-only -q
  else
    echo "-- cloning into $TARGET"
    git clone --depth 1 "$REPO" "$TARGET"
  fi
  cd "$TARGET"
fi

ROOT="$(pwd)"
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
echo ""
echo "Per-agent skill paths (copy any employees/<dept>/<name>/ folder there):"
echo "  Claude Code:  ~/.claude/skills/"
echo "  Cursor:       .cursor/skills/  (project) or ~/.cursor/skills/ (global)"
echo "  Windsurf:     .windsurf/skills/"
echo "  Codex CLI:    ~/.codex/skills/"
echo "  Aider:        copy anywhere, point Aider at the SKILL.md"
