---
name: fleet-dispatcher
description: Dispatches work to Solaris headless worker machines and checks on them using project-local fleet state. Fires on "send this to m1/mN", "dispatch to fleet/worker", "check m1", "fleet status", "sync fleet", "is the stream done", or "bounce it back". Provider-neutral. Never reads control-Mac Desktop/the coding agent personal-data paths; never silent-deploys or rewrites git history.
---

# Fleet Dispatcher

Provider-neutral fleet dispatch for Solaris professional work. Authority and tools are granted only by `capability.contract.json` - prose never grants tools or personal-path access.

**Step 0 - Read project-local fleet doctrine first.** Preferred sources (in order):

1. `$SOLARIS_FLEET_ROOT/FLEET.md` when `SOLARIS_FLEET_ROOT` is set  
2. `project/fleet/FLEET.md` inside the active workspace  
3. Synthetic fixture under `fixtures/solaris/technical/fleet/` for tests only  

**Hard ban:** do **not** read or require control-Mac personal Desktop skill trees, Alfred personal stores, or other personal-data directories. Those locations are out of scope for this capability (hard control). If only personal paths exist, emit a **blocked** envelope and ask for a project-local fleet root.

## OUTPUT CONTRACT

Every dispatch/status deliverable uses this exact shape:

1. **Fleet root used** - absolute or workspace-relative path actually read (must be project-local or `SOLARIS_FLEET_ROOT`, never a personal Desktop path).  
2. **Action taken** - dispatch | status | bounce | escalate - with worker alias and SSH login from the roster file.  
3. **Artifacts** - WORK-ORDER path, branch name, log path, or status table.  
4. **Evidence** - real command output (or blocked reason); no phantom credits.  
5. **Gate line** - end with literal `Gate: passed` only when SELF-QA all yes.

## SELF-QA GATE (mandatory before reply)

1. Fleet doctrine read from an **allowed** root this session (not from memory)?  
2. Zero reads of Desktop/the coding agent personal-data or Alfred personal stores?  
3. Executed host commands yourself when tools available - not “paste this, Shai” as the only path?  
4. SSH login taken from roster column, not guessed?  
5. Launcher/token pattern machine-local only - no tokens in git, chat, or shared iCloud skill bundles?  
6. Completion claims backed by artifacts (gate line + evidence files)?  
7. No silent production deploy, credential commit, or force-push / history rewrite?  
8. No phantom credits?

Any no → fix or **BLOCKED**. End successful deliverables with: `Gate: passed`

## HARD NUMBERS

| Figure | Rule |
|--------|------|
| 0 | Silent production deploys allowed |
| 0 | Force-pushes as recovery default |
| 0 | Credentials/tokens written to git |
| 0 | Desktop/the coding agent personal-path dependencies |
| 2 | Max bounce rounds before escalate to human |
| 1 | Source of truth for roster: declared fleet root only |

## When to invoke

- **Me** - dispatch/monitor/review fleet streams using project-local fleet state  
- **fleet-provisioner** - turn a machine into a worker (separate capability)  
- **devops-engineer** - CI/CD and IaC (not stream dispatch)  
- **Gas Town** - when `gt sling` / convoy is the active control plane, prefer that over manual stream recipes  

## Five laws (provider-neutral)

1. **You execute** via granted host tools when present. If host tools are unavailable, fail closed with `PREFLIGHT_FAILED` / unavailable-tool evidence - do not invent success.  
2. **SSH uses the roster login** from the allowed fleet root. Never invent usernames or require personal Desktop files.  
3. **Streams never run naked provider CLIs without machine-local token files** outside git. Tokens stay machine-local Keychain/file with mode 600; never in the skill bundle.  
4. **Workers are vanilla until armed** - push only the skills named in the work order from a signed/published bundle, not personal Desktop trees.  
5. **Verify from artifacts, never claims** - gate line, SKILL-EVIDENCE (or equivalent), tests actually run, white-label commit messages clean.

## Work-order minimum

Every dispatched branch carries `WORK-ORDER.md`: scope, interface contract, definition of done, forbidden files, skills to read (Step-0), commit rules (no AI co-author stamps), PR target, and mandatory closer `Gate: passed`.

## Monitoring (project-local only)

- Status: read `project/fleet/status.json` or run the **project-declared** watch script under `project/fleet/ops/` (or `$SOLARIS_FLEET_ROOT/ops/`).  
- Sync: run the **project-declared** sync entrypoint under the same roots.  
- If those scripts are missing → **blocked**, do not fall back to personal Desktop paths.

## Process flow

```
SPEC → DISPATCH (WORK-ORDER on branch, skills armed) → BUILD (Gate: passed)
  → REVIEW (artifacts only) → BOUNCE (max 2) or ESCALATE (human)
  → MERGE (human only) → NEXT ROUND
```

Gas Town: rigs under `~/gt/<rig>` are separate clones - never two agents on one branch. Prefer `gt sling` / convoy when available.

## Scope protection

| Request | Required behavior |
|---------|-------------------|
| Silent production deploy | **Refuse** - deploy is deny / require_human |
| Commit secrets or tokens | **Refuse** |
| Force-push / history rewrite | **Refuse** (default) |
| Read control-Mac personal Desktop skill trees | **Refuse** - blocked; demand project fleet root |
| Missing fleet tools/scripts | **Blocked** envelope - unavailable-tool |

## Provider policy

Compatible with the project runtime adapters. Adapters must not change authority, permissions, acceptance, data policy, tools, failure, or evidence (`capability.contract.json`).

## Rollback / recovery

- Preserve partial dispatch notes on disk.  
- Never force-push to recover a bad stream; open a new branch or ask human.  
- Revoked tokens → blocked until human rotates machine-local credentials.

Load `capability.contract.json` for grants. Log durable lessons only via reviewed `learnings.md` when present.
