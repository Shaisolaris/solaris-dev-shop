#!/bin/sh
# M02 r2 fresh-caller transfer (Grok self-validation). Run from the repo root: sh m02r2_fresh_caller.sh <python>
# A fresh caller with an empty HOME and minimal env follows only SKILL.md's commands and the tool's own messages.
P="$1"; TOK="ghp_$(printf "Ab12%.0s" 1 2 3 4 5 6 7 8 9)"  # synthetic, built at run time
A=employees/product-project/project-onboarding/activate.py
H=$(mktemp -d /tmp/m02r2-fc-XXXXXX); export HOME="$H"
OUTF=$(mktemp /tmp/m02r2-fcout-XXXXXX)
run() { echo "\$ activate.py $*" | sed -e "s#$H#<FCHOME>#g" -e "s#$TOK#ghp_<synthetic>#g"; env -i HOME="$H" PATH="/usr/bin:/bin" "$P" "$A" "$@" > "$OUTF" 2>&1; rc=$?; sed "s#$H#<FCHOME>#g" "$OUTF"; echo "[rc $rc]"; }
echo "# fresh caller: env -i, HOME empty temp dir, $("$P" -V)"
echo "## 1 existing live client project is used as a template for a new client (the F1 scenario)"
mkdir -p "$H/clients"; run activate "$H/clients/acme" --name "Acme" --type "web app" --deploy-model "production: main=live"
cp -R "$H/clients/acme" "$H/clients/bolt"
run activate "$H/clients/bolt" --name "Bolt" --type website
echo "STATUS deploy line: $(grep '^DEPLOY-MODEL:' "$H/clients/bolt/STATUS.md")"
run resume "$H/clients/bolt"
echo "## 2 owner then states Bolt's own deploy model"
run activate "$H/clients/bolt" --name "Bolt" --type website --deploy-model "preview only"
echo "## 3 a killed run left a lock and a temp file; follow the message"
: > "$H/clients/bolt/.solaris-activation.lock"; echo junk > "$H/clients/bolt/.STATUS.md.00112233aabbccdd.activation-tmp"
run resume "$H/clients/bolt"
rm "$H/clients/bolt/.solaris-activation.lock"; run resume "$H/clients/bolt"
echo "temp files left: $(find "$H/clients" -name '*.activation-tmp' | wc -l | tr -d ' ')"
echo "## 4 a commit id in the brief and a pasted token"
run activate "$H/clients/bolt" --name "Bolt" --brief "fork of 41132041afeb2cce63a68554caf18cf6992a11ae"
run activate "$H/clients/bolt" --name "Bolt" --credential "system=github;location=$TOK"
rm -rf "$H" "$OUTF"; echo "temp HOME removed: $([ -e "$H" ] && echo no || echo yes)"
