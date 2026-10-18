#!/bin/sh
# M02 fresh-caller transfer: a new caller with an empty environment and a new HOME, who knows only
# project-onboarding/SKILL.md. It extracts the documented commands, fills the placeholders, runs them,
# then follows the documented recovery for a failed write and for a killed run.
# Usage (from the repository root): env -i HOME=<new> PATH=<python3 dir>:/usr/bin:/bin sh m02_fresh_caller.sh
set -u
SKILL=employees/product-project/project-onboarding/SKILL.md
echo "# env: $(env | wc -l | tr -d ' ') vars; HOME=$HOME; python3=$(command -v python3) ($(python3 -V 2>&1))"
echo "# documented commands (verbatim from SKILL.md):"
awk '/^```bash/{f=1;next}/^```/{f=0}f' "$SKILL"
ACT=$(awk '/^```bash/{f=1;next}/^```/{f=0}f' "$SKILL" | grep -m1 'activate.py activate' | sed 's/ <project-root>.*//')
RES=$(awk '/^```bash/{f=1;next}/^```/{f=0}f' "$SKILL" | grep -m1 'activate.py resume' | sed 's/ <project-root>.*//')
ROOT="$HOME/clients/harbor"
mkdir -p "$HOME/clients"
echo "# 1. activate with intake answered except the deploy model (owner gave none)"
$ACT "$ROOT" --name "Harbor Tours" --type "website" --brief "Booking site" \
  --credential "system=github;username=harbor-bot;location=1Password/Eng/GitHub"; echo "[exit $?]"
echo "# 2. identical rerun changes nothing"
before=$(find "$ROOT" -type f -exec shasum -a 256 {} + | sort | shasum -a 256)
$ACT "$ROOT" --name "Harbor Tours" --type "website" --brief "Booking site" \
  --credential "system=github;username=harbor-bot;location=1Password/Eng/GitHub" >/dev/null; echo "[exit $?]"
after=$(find "$ROOT" -type f -exec shasum -a 256 {} + | sort | shasum -a 256)
[ "$before" = "$after" ] && echo "RERUN BYTE-IDENTICAL: yes" || echo "RERUN BYTE-IDENTICAL: NO"
grep -n '^DEPLOY-MODEL:' "$ROOT/STATUS.md"
echo "# 3. owner states the deploy model; a write fails (read-only Scope/); fix the cause and run resume"
chmod 555 "$ROOT/Scope"
$ACT "$ROOT" --name "Harbor Tours" --deploy-model "Netlify, owner approves each release"; echo "[exit $?]"
chmod 755 "$ROOT/Scope"
$RES "$ROOT"; echo "[exit $?]"
grep -c 'Netlify, owner approves each release' "$ROOT/STATUS.md" "$ROOT/Scope/ROUND-PLAN.md"
echo "# 4. a killed run: lock left behind; the message names it; owner deletes it and resumes"
printf '{"pid": 999999, "host": "%s", "started": "earlier"}' "$(python3 -c 'import socket;print(socket.gethostname())')" > "$ROOT/.solaris-activation.lock"
$RES "$ROOT"; echo "[exit $?]"
rm "$ROOT/.solaris-activation.lock"
$RES "$ROOT"; echo "[exit $?]"
echo "# 5. secret value refused, not echoed"
$ACT "$ROOT" --name "Harbor Tours" --credential "system=aws;username=ci;location=AKIA$(printf 'Q%.0s' 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16)" 2>&1 | grep -v AKIA; echo "[exit (pipeline) see above; token lines filtered: $($ACT "$ROOT" --name "Harbor Tours" --credential "system=aws;username=ci;location=AKIA$(printf 'Q%.0s' 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16)" 2>&1 | grep -c AKIA)]"
echo "# resulting tree"
(cd "$ROOT" && find . | sort)
