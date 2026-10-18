#!/bin/sh
# M02 finding reproductions. Run from the repository root at the candidate commit:
#   PY=<python3.12> sh m02_finding_repros.sh
# Every case uses a fresh mktemp directory and synthetic values only.
PY=${PY:-python3}
A=employees/product-project/project-onboarding/activate.py
T=$(mktemp -d "${TMPDIR:-/tmp}/m02-repro.XXXXXX")
x() { echo "\$ $*"; "$@" > "$T/.out" 2>&1; rc=$?; sed -n '1,6p' "$T/.out"; echo "[exit $rc]"; }
xt() { echo "\$ $*"; "$@" > "$T/.out" 2>&1; rc=$?; tail -1 "$T/.out"; grep -c 'Traceback' "$T/.out" | sed 's/^/traceback lines: /'; echo "[exit $rc]"; }

echo "== F1 copied project folder: omitted deploy answer inherits another project's live deploy model"
x $PY $A activate "$T/alpha" --name "Alpha Corp" --type "web app" --deploy-model "production: main=live"
cp -R "$T/alpha" "$T/gamma"
x $PY $A activate "$T/gamma" --name "Gamma Inc" --type website
grep '^DEPLOY-MODEL' "$T/gamma/STATUS.md"
echo "-- journal-only copy into a new client folder"
mkdir "$T/beta"; cp "$T/alpha/.solaris-activation.json" "$T/beta/"
$PY $A activate "$T/beta" --name "Beta Ltd" --type website --json | $PY -c "import json,sys;r=json.load(sys.stdin);print('status',r['status'],'inherited',r['inherited'],'deploy',r['intake']['deploy_model'])"

echo "== F2 invisible-only deploy answer is recorded as resolved (U+200B, U+FEFF)"
x $PY $A activate "$T/zw" --name "ZW" --type "web app" --deploy-model "$(printf '\342\200\213')"
grep '^DEPLOY-MODEL' "$T/zw/STATUS.md" | od -c | sed -n 1,2p
x $PY $A activate "$T/bom" --name "BOM" --type "web app" --deploy-model "$(printf '\357\273\277')"
echo "-- invisible-only required name"
x $PY $A activate "$T/zwname" --name "$(printf '\342\200\213')" --deploy-model none

echo "== F3 literal answer UNRESOLVED: file says UNRESOLVED, status says complete"
x $PY $A activate "$T/ur" --name "UR" --type "web app" --deploy-model "UNRESOLVED"
grep '^DEPLOY-MODEL' "$T/ur/STATUS.md"

echo "== F4 uncaught exceptions instead of a result (nothing is written in any of these)"
mkdir "$T/ro"; chmod 555 "$T/ro"
xt $PY $A activate "$T/ro" --name "RO" --json
chmod 755 "$T/ro"
mkdir "$T/cj"; printf '%s' '{"schema":"solaris.project-activation/1","intake":{"name":"X"},"files":{"STATUS.md":["a"]}}' > "$T/cj/.solaris-activation.json"
xt $PY $A resume "$T/cj" --json
mkdir "$T/cj2"; printf '%s' '{"schema":"solaris.project-activation/1","intake":{"name":"X"},"files":{"STATUS.md":{"pending":["x"]}}}' > "$T/cj2/.solaris-activation.json"
xt $PY $A activate "$T/cj2" --name X --json
LONG=$($PY -c "print('x'*300)")
xt $PY $A activate "$T/$LONG" --name "Long" --json

echo "== F5 SIGKILL leaves hidden temp files that the documented recovery does not remove"
echo "(see raw/oracle-candidate.txt k6 WARN lines and raw/adversarial-candidate.txt a12 for the injected-kill runs)"

echo "== F6 empty lock (kill between lock create and pid write) is not reported as stale"
x $PY $A activate "$T/el" --name EL --deploy-model none
: > "$T/el/.solaris-activation.lock"
x $PY $A resume "$T/el"

echo "== F7 DEPLOY-MODEL marker text in the name precedes the real line"
x $PY $A activate "$T/inj" --name "Acme DEPLOY-MODEL: main=live"
grep -n 'DEPLOY-MODEL:' "$T/inj/STATUS.md"

echo "== F8 a 40-hex commit id in the brief is refused as a secret"
x $PY $A activate "$T/sha" --name SHA --brief "fork of 41132041afeb2cce63a68554caf18cf6992a11ae"

chmod -R u+w "$T" 2>/dev/null; rm -rf "$T"
echo "removed temp dir"
