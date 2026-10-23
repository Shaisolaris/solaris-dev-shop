#!/usr/bin/env bash
# Solaris Dev Shop explicit, checkout-only install.
#
# From a checkout:   ./install.sh
# Review and select the checkout revision before running this script.
# Uninstall:         ./install.sh --uninstall
#
# Verifies the tree, runs the control-plane self-test, and links the
# `solaris-intake` command into ~/.local/bin.
set -euo pipefail

INSTALL_BIN_DIR="$HOME/.local/bin"
UNINSTALL=false
PYTHON_BIN="${SOLARIS_PYTHON:-python3}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --uninstall) UNINSTALL=true; shift ;;
    --bin-dir)
      [ "$#" -ge 2 ] || { echo "--bin-dir requires a directory" >&2; exit 2; }
      INSTALL_BIN_DIR="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [ "$UNINSTALL" = true ]; then
  if [ -f "$INSTALL_BIN_DIR/solaris-intake" ] && grep -Fq '# Solaris Dev Shop managed command' "$INSTALL_BIN_DIR/solaris-intake"; then
    rm -f "$INSTALL_BIN_DIR/solaris-intake"
    echo "Removed the Solaris Dev Shop command."
  elif [ -e "$INSTALL_BIN_DIR/solaris-intake" ]; then
    echo "Kept an unrecognized command at $INSTALL_BIN_DIR/solaris-intake; inspect it before removing it."
  else
    echo "No managed command found."
  fi
  echo "Source checkout and local files retained; uninstall removes only the managed command."
  exit 0
fi

if [ -L "$INSTALL_BIN_DIR/solaris-intake" ] || { [ -e "$INSTALL_BIN_DIR/solaris-intake" ] && ! grep -Fq '# Solaris Dev Shop managed command' "$INSTALL_BIN_DIR/solaris-intake"; }; then
  echo "Refusing to overwrite an unrecognized command at $INSTALL_BIN_DIR/solaris-intake" >&2
  exit 1
fi

"$PYTHON_BIN" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else "Solaris Dev Shop requires Python 3.10 or newer. Set SOLARIS_PYTHON to its executable.")'

# Installation never fetches code or advances an existing checkout.
if [ ! -f "control-plane/meta_control_plane.py" ]; then
  echo "Run install.sh from the root of a reviewed Solaris Dev Shop checkout. No code was downloaded or updated." >&2
  exit 1
fi

ROOT="$(pwd)"
cd "$ROOT"

echo "== Solaris Dev Shop =="
echo "-- checking tree"
for f in control-plane/meta_control_plane.py control-plane/roster.json control-plane/policy.json chief-of-staff/SKILL.md; do
  [ -f "$f" ] || { echo "missing: $f"; exit 1; }
done
count=$(find employees -maxdepth 3 -name SKILL.md | wc -l | tr -d ' ')
echo "   employee skills: $count"

echo "-- control-plane self-test"
"$PYTHON_BIN" control-plane/meta_control_plane.py self-test

echo "-- routing probes"
"$PYTHON_BIN" -m unittest discover -s tests -v 2>&1 | tail -4

echo "-- installing solaris-intake"
mkdir -p "$INSTALL_BIN_DIR"
{
  printf '#!/usr/bin/env bash\n# Solaris Dev Shop managed command\nexec '
  printf '%q ' "$PYTHON_BIN" "$ROOT/control-plane/meta_control_plane.py"
  printf '"$@"\n'
} > "$INSTALL_BIN_DIR/solaris-intake"
chmod +x "$INSTALL_BIN_DIR/solaris-intake"

echo ""
echo "Done. Try:"
echo "  solaris-intake intake \"Write a test plan for the client portal login regression\""
case ":$PATH:" in
  *":$INSTALL_BIN_DIR:"*) ;;
  *) echo "  (add $INSTALL_BIN_DIR to your PATH to use solaris-intake anywhere)" ;;
esac
echo ""
echo "Per-agent skill paths (preserve companion files and shared-standard references):"
echo "  Claude Code:  ~/.claude/skills/"
echo "  Cursor:       .cursor/skills/  (project) or ~/.cursor/skills/ (global)"
echo "  Windsurf/Devin: .devin/skills/ (.windsurf/skills/ remains a legacy path)"
echo "  Codex:        .agents/skills/ (project) or ~/.agents/skills/ (user)"
echo "  Aider:        copy anywhere, point Aider at the SKILL.md"
