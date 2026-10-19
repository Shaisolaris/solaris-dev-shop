#!/bin/zsh
# M07 fresh caller (Grok self-validation): copy of the candidate tree (no .git), env -i with a new HOME, a PATH shim
# mapping python3 to the given Python, then only the commands in examples/capabilities/G07/README.md (Try it), then the
# README's work-order sentence (G04 order with a fleet block, --identity, SOLARIS_FLEET_ROOT). Usage: PY TREE
P=$1; C=$2; F=/tmp/m07-fresh; rm -rf $F; mkdir -p $F/home $F/bin; rsync -a --exclude .git --exclude __pycache__ $C/ $F/repo/; ln -s $P $F/bin/python3
cat > $F/caller.sh <<'IN'
set -u; repo=$HOME/../repo
mkdir /tmp/m07-fresh/g07-demo && cd /tmp/m07-fresh/g07-demo && cp -R $repo/examples/capabilities/G07/fixtures id && mkdir fleet
R=$repo/employees/infrastructure/fleet-provisioner/registry.py
x() { want=$1; shift; python3 "$@" >/dev/null 2>&1; rc=$?; echo "rc=$rc want=$want $([ $rc = $want ] && echo OK || echo MISMATCH) :: ${*#$R }"; }
x 0 $R register --root fleet --alias mini1 --identity id/identity-mini1.json --owner ana --request-id reg-1
x 0 $R register --root fleet --alias mini1 --identity id/identity-mini1.json --owner ana --request-id reg-1
x 2 $R register --root fleet --alias spare --identity id/identity-mini1.json --owner ben --request-id reg-2
x 2 $R claim --root fleet --alias mini1 --identity id/identity-impostor.json --owner ana --epoch 1
x 75 $R transfer --root fleet --alias mini1 --from-owner ana --expect-epoch 1 --to-owner ben --request-id t-1 --fail-at before-replace
x 0 $R claim --root fleet --alias mini1 --identity id/identity-mini1.json --owner ana --epoch 1
x 0 $R transfer --root fleet --alias mini1 --from-owner ana --expect-epoch 1 --to-owner ben --request-id t-1
x 2 $R claim --root fleet --alias mini1 --identity id/identity-mini1.json --owner ana --epoch 1
python3 $R status --root fleet; echo "status rc=$?"
# README: a G04 order bound to a machine; the order owner must be the machine's current owner (doc), so transfer to it first
x 0 $R transfer --root fleet --alias mini1 --from-owner ben --expect-epoch 2 --to-owner "delivery-lead: A. Example" --request-id t-2
cp -R $repo/examples/capabilities/G04/fixtures wo && python3 - <<'PY'
import json; p="wo/order.json"; o=json.load(open(p)); o["fleet"]={"machine":"mini1","owner_epoch":3}; json.dump(o,open(p,"w"))
PY
H=$repo/employees/infrastructure/fleet-dispatcher/handoff.py
cd wo; SOLARIS_FLEET_ROOT=../fleet python3 $H run order.json --worker ana --identity ../id/identity-mini2.json >/dev/null 2>&1; echo "wrong machine order rc=$? want=2"
SOLARIS_FLEET_ROOT=../fleet python3 $H run order.json --worker ana --identity ../id/identity-mini1.json >/dev/null 2>&1; echo "right machine order rc=$? want=0"; wc -l < outbox/ledger.jsonl
IN
env -i HOME=$F/home PATH=$F/bin:/usr/bin:/bin /bin/bash $F/caller.sh
echo "python3 = $($F/bin/python3 -c 'import sys;print(sys.version.split()[0])'); pycache dirs left in the repo copy:"; find $F/repo -name __pycache__ | sed "s#$F/repo/##"
rm -rf $F
