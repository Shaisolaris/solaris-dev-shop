#!/bin/sh
# M02 r2 residual repros (Grok self-validation). From the repo root: sh m02r2_finding_repros.sh <python>
P="$1"; A=employees/product-project/project-onboarding/activate.py; T=$(mktemp -d /tmp/m02r2-rep-XXXXXX)
export LC_ALL=C
r() { echo "\$ $*" | sed "s#$T#<T>#g"; "$P" "$A" "$@" > "$T/.o" 2>&1; rc=$?; grep -h '^  "status"' "$T/.o"; tail -1 "$T/.o" | cut -c1-160 | sed "s#$T#<T>#g"; echo "[rc $rc]"; }
echo "## P3-1a deeply nested journal: traceback instead of a blocked result"
mkdir "$T/deep"; "$P" -c "open('$T/deep/.solaris-activation.json','w').write('['*200000)"; r activate "$T/deep" --name Deep --json; r resume "$T/deep" --json
echo "## P3-1b deeply nested lock file"
mkdir "$T/dlock"; "$P" -c "open('$T/dlock/.solaris-activation.lock','w').write('['*200000)"; r activate "$T/dlock" --name D --json
echo "## P3-1c non-UTF-8 byte in the name (shell paste from a Latin-1 source)"
r activate "$T/bad" --name "$(printf 'Caf\351')" --type "web app" --json; echo "root created: $([ -e "$T/bad" ] && echo yes || echo no)"
echo "## P4-1 visually blank deploy answers still count as resolved"
for v in "$(printf '\343\205\244')" "$(printf '\342\240\200')" "$(printf '\314\201')"; do r activate "$T/v$(printf %s "$v" | od -An -tx1 | tr -d ' \n')" --name V --type "web app" --deploy-model "$v" --json; done
grep -h '^DEPLOY-MODEL' "$T"/v*/STATUS.md | od -c | head -4
echo "## P4-2 UNRESOLVED behind an invisible or fullwidth character is accepted as an answer"
r activate "$T/u1" --name U --type "web app" --deploy-model "$(printf '\342\200\213UNRESOLVED')"; grep '^DEPLOY-MODEL' "$T/u1/STATUS.md"
r activate "$T/u2" --name U --type "web app" --deploy-model "ＵＮＲＥＳＯＬＶＥＤ"; grep '^DEPLOY-MODEL' "$T/u2/STATUS.md"
echo "## P4-3 sha256 + 64-hex in the brief is refused (the doc's sha + 64 hex works)"
r activate "$T/s1" --name S --brief "sha256 62614bb3a1e36aa009a623e9b40600349c0e6b8fc2b3a8b506a941f43db3cd74"
r activate "$T/s2" --name S --brief "sha 62614bb3a1e36aa009a623e9b40600349c0e6b8fc2b3a8b506a941f43db3cd74"
echo "## P4-4 a moved project folder can no longer resume (journal bound to the old path)"
r activate "$T/m" --name M --type "web app" --deploy-model "main"; mv "$T/m" "$T/m2"; r resume "$T/m2"
rm -rf "$T"
