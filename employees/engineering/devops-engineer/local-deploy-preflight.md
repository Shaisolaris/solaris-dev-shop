# Local deploy preflight and rollback drill (local_deploy.py)

For disposable local fixtures only: a target folder whose `ENVIRONMENT.json` says `"kind": "local-fixture"`.
It rehearses the deploy discipline in SKILL.md (rollback before forward, approval before apply, health
before and after) with real files and a real SQLite dataset. It uses no cloud account, secret, network call
or billable resource, and it does not replace a provider's deploy tooling for real environments.

## Layout

```
plan.json            schema solaris.deploy-plan/1: environment, target, artifact {path, revision, sha256},
                     health {required_files, databases}
approval.json        schema solaris.deploy-approval/1: action, environment, revision, artifact_sha256 (deploy
                     only), approved_by
env/ENVIRONMENT.json schema solaris.local-environment/1: name, kind "local-fixture"
env/releases/<rev>/  one folder per release; env/current is a relative link to the live one
env/data/*.db        the dataset; snapshots, verification and restores use G03 sqlite_recovery.py
env/.deploy/         journal.json (only while a deploy is in flight), history.jsonl, snapshots/<deploy_id>
```

An artifact folder holds `REVISION`, its files, optionally `migrate.sql` (applied to the first database in
one transaction) and `health.json` (`{"user_version": N}`: the data must be at that schema version).

## Commands

```bash
T=employees/engineering/devops-engineer/local_deploy.py
python3 $T digest artifact-r2                                   # the sha256 to pin in the plan and approval
python3 $T preflight plan.json --approval approval.json         # read-only; exit 0 only if every check passes
python3 $T deploy plan.json --approval approval.json            # 0 deployed, 1 failed health and rolled back
python3 $T rollback plan.json --approval rollback-approval.json # back to the previous release and its data
python3 $T recover plan.json                                    # finish rolling back an interrupted deploy
python3 $T status plan.json --json
```

Exit codes: 0 done; 1 rolled back (health failed, or `recover` undid an interrupted deploy); 2 refused or
invalid, nothing changed; 75 a `--fail-at staged|migrated|switched` crash drill.

## Preflight checks (all read-only; any failure refuses the deploy before a single write)

1. **environment**: ENVIRONMENT.json names the plan's environment and is a local fixture.
2. **artifact**: REVISION equals the plan's revision; the content digest equals the plan's sha256; no
   symlink and no secret-like file (`.env`, `*.pem`, `*.key`, `id_rsa*`, `credentials.json`, `*.p12`).
3. **authority**: an approval file for action `deploy` naming this environment, revision and digest, and who
   approved it. A rollback needs its own approval naming the revision returned to.
4. **health**: the live release passes its health check (required files present and non-empty, G03 health
   on the databases, the schema version in health.json). A broken live release is fixed or rolled back first.
5. **rollback**: the live release still matches the digest recorded when it was deployed; the databases can
   be snapshotted; no unfinished deploy is pending; the release folder is new (or holds this exact artifact).

## What deploy does after preflight

Snapshot and verify the data (G03), record the journal, stage and verify the release, apply `migrate.sql`
in one transaction, switch `current` atomically, run the health check on the new release. On failure it
restores the data from the snapshot (G03 restore keeps the replaced file as `*.pre-restore-*`), switches back
and moves the failed release to `releases/.failed-<rev>-<deploy_id>`. A repeated deploy of the live release
with the same artifact changes nothing.

## Limits

- Data written between a deploy and a later explicit `rollback` is replaced by the pre-deploy snapshot (the
  replaced file is kept by G03). Stop writers before deploying or rolling back.
- One deployer at a time; there is no lock between two concurrent deploys of the same target.
- Not run: any real host, container, cloud provider, DNS, CDN or traffic switch.
