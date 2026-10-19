# G08 local deployment preflight and safe rollback

`employees/engineering/devops-engineer/local_deploy.py` validates the intended environment, artifact revision
and digest, approval, live health and rollback availability before touching a disposable local fixture,
then deploys with a G03 data snapshot, atomic switch, post-deploy health check and automatic rollback. See
`local-deploy-preflight.md` in devops-engineer.

## Try it (fresh folder; nothing outside it is touched)

```bash
python3 examples/capabilities/G08/make_world.py /tmp/g08-demo && cd /tmp/g08-demo
T=<repo>/employees/engineering/devops-engineer/local_deploy.py
python3 $T deploy plan-r1.json                                             # exit 2: no approval, nothing changed
python3 $T deploy plan-r1.json --approval approval-r1.json                 # exit 0: first deploy
python3 $T deploy plan-r2.json --approval approval-r2.json                 # exit 0: r2 live, schema version 2
python3 $T deploy plan-r3-broken.json --approval approval-r3-broken.json   # exit 1: health failed, back on r2 and r2 data
python3 $T deploy plan-r3-broken.json --approval approval-r3-broken.json --fail-at migrated   # exit 75: crash drill
python3 $T deploy plan-r2.json --approval approval-r2.json                 # exit 2: unfinished deploy pending
python3 $T recover plan-r2.json                                            # exit 1: interrupted deploy rolled back
python3 $T deploy plan-r2.json                                             # exit 2: r2 already live, a repeat still needs approval
python3 $T rollback plan-r2.json --approval approval-rollback-to-r1.json   # exit 0: r1 and its data again
```

## Oracle and controls

```bash
python3 examples/capabilities/G08/deploy_oracle.py                                              # 18/18
python3 examples/capabilities/G08/deploy_oracle.py --tool examples/capabilities/G08/naive_deploy.py  # 3/18
python3 examples/capabilities/G08/deploy_oracle.py --tool examples/capabilities/G08/noop_deploy.py   # 1/18
```

Each scenario builds a fresh world. Refusals are judged by a byte-level comparison of the whole environment
tree before and after; data is read with sqlite3 directly. `naive_deploy.py` copies, migrates and switches
with no checks, snapshot or rollback (it passes the clean control, the repeat deploy and the static check).
`noop_deploy.py` does nothing. o14 runs 12 seeded cycles of upgrades, failing deploys, crash drills,
recoveries and rollbacks and checks after each that the live release and the data schema agree.
o16 holds the target lock and expects deploy, rollback and recover to be refused with the tree unchanged, then
races two deploys of r3-broken 15 times (both must end on r2 with r2's data and nothing pending) and two
deploys of r2 from r1 8 times (exactly one deploy recorded). o17: a repeat deploy of the live release is
refused without approval or with the wrong one, succeeds unchanged when approved and healthy, and is refused
once an outside writer breaks the live schema version.

Not run: real hosts, containers, cloud providers, DNS or traffic switching.
