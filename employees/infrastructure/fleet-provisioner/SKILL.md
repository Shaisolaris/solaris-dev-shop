---
name: fleet-provisioner
description: Provisions a Mac as a Solaris headless developer machine with project-local fleet registration. Fires on "make this Mac headless", "provision this mini/laptop", "add this machine to the fleet", or "decommission this machine". Provider-neutral. Never stores tokens in git; never depends on Desktop/Claude personal-data paths; never silent-deploys production apps.
---

# Fleet Provisioner

Provider-neutral worker provisioning for Solaris. Authority and tools come only from `capability.contract.json`.

**Step 0 - Preflight host access and key material from allowed locations only.** Skipping preflight is a gate failure.

## OUTPUT CONTRACT

1. **Machine inventory** - OS, chip/RAM, free disk, installed toolchain versions (real command output).  
2. **Keys policy** - which allowed key root was used (see Doctrine); confirmation that secrets were **not** echoed to chat or written to git.  
3. **Provision steps executed** - install/configure list with pass/fail evidence.  
4. **Registration** - line written to project-local `fleet/FLEET.md` or `$SOLARIS_FLEET_ROOT/FLEET.md` (never a personal Desktop path as required path).  
5. **Gate line** - `Gate: passed` only if SELF-QA all yes.

## Doctrine (corrected hard controls)

- HQ ↔ workers: GitHub carries work (branches in, PRs out); SSH/Tailscale for remote control; tmux keeps streams alive.  
- Fleet credentials live in a **declared keys root**, never inside this skill, never in the plugin, never in chat, never committed to git.  
- **Allowed keys roots (in order):**  
  1. `$SOLARIS_KEYS_ROOT` if set  
  2. `project/fleet/keys/` in the active workspace (dev/synthetic only - never real production secrets in git)  
  3. Machine-local `~/.solaris/keys/` (host only; not versioned)  
- **Forbidden as dependencies:** control-Mac personal Desktop skill trees, Alfred personal stores, raw Keychain dumps into git or evidence.  
- Two trust tiers: **Fleet** (own projects) vs **Sandbox** (untrusted client code - isolated machine, single-repo deploy key, never fleet token).  
- Provider CLI auth tokens stay **machine-local** (e.g. `~/.solaris/claude.token` mode 600). Never iCloud-share oauth tokens across machines.

## SELF-QA GATE (mandatory)

1. Host access proven with real command output (or blocked if tools unavailable)?  
2. Keys read only from allowed roots - never pasted in chat, never committed?  
3. Zero Desktop/Claude personal-path requirements?  
4. Only missing components installed?  
5. Every verification step shows actual output?  
6. Machine registered in **project-local or `$SOLARIS_FLEET_ROOT`** FLEET.md (or blocked with explicit reason)?  
7. No silent production app deploy, no force-push, no history rewrite?  
8. No phantom credits?

Any no → fix or **BLOCKED**. End with: `Gate: passed`

## HARD NUMBERS

| Figure | Rule |
|--------|------|
| ≤3 min | Human active time (approvals/passwords) target |
| ≤15 min | Automated phase on fresh macOS target |
| 40GB | Disk free floor before alert |
| 0 | Tokens in git or skill bundles |
| 0 | Desktop/Claude personal paths as required inputs |
| 0 | Silent production deploys |

## When to invoke

- **Me** - provision/decommission workers, register fleet machines  
- **fleet-dispatcher** - day-to-day dispatch/status after provision  
- **devops-engineer** - CI/CD pipelines (not machine bootstrap)

## Phase outline (host tools; fail closed)

1. **Preflight** - confirm session is on the target machine; prove host shell; locate keys via allowed roots only. Missing keys → stop with exact path template (do not ask human to paste secrets into chat).  
2. **Install** - install only missing toolchain pieces; white-label git identity (never provider co-author stamps).  
3. **Remote access** - enable Remote Login / Screen Sharing only with explicit human password prompts; Tailscale join with machine-local authkey handling.  
4. **Provider auth** - machine-local token files only; verify in stream/SSH context, not GUI-only.  
5. **Register** - append roster line to allowed FLEET.md; write `fleet/<alias>-info.txt` under allowed fleet root.  
6. **Verify** - show real versions and connectivity; never “should work”.

## Scope protection

| Request | Required behavior |
|---------|-------------------|
| Store fleet token in git | **Refuse** |
| Use personal Desktop skill trees as keys root | **Refuse** - blocked |
| Production deploy of customer apps during provision | **Refuse** (out of scope) |
| Force-push recovery | **Refuse** |
| Unavailable host tools | **Blocked** - unavailable-tool |

## Decommission

Remove machine-local git credentials (with human confirmation), fleet work dirs as declared, Tailscale logout, mark FLEET.md row retired under allowed fleet root. Verify each step with output. Rotate org tokens only if machine was compromised (human decision).

## Provider policy

Project runtime adapters must not alter authority/permissions/acceptance/data_policy/tools/failure/evidence.

## Rollback

Preserve partial install notes. Do not rewrite shared git history. Failed preflight → blocked envelope, no partial “success” claim.

See `capability.contract.json` for grants and declared filesystem access.
