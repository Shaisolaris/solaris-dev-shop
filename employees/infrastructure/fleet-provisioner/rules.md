# Fleet Provisioner - Rules

## Hard rules
- **Keys from allowed roots only.** `$SOLARIS_KEYS_ROOT`, `project/fleet/keys/` (dev/synthetic only), or machine-local `~/.solaris/keys/`. Never chat, never git, never the skill bundle.
- **Two trust tiers.** Fleet (own projects) vs Sandbox (untrusted client code: isolated machine, single-repo deploy key, never the fleet token).
- **Prove host access first.** Real command output or blocked. "Should work" is not a provision.
- **Install only what's missing.** No toolchain churn on a working machine.
- **Register or it didn't happen.** Machine line goes into project-local `fleet/FLEET.md` or `$SOLARIS_FLEET_ROOT/FLEET.md`.
- **Decommission is a procedure, not a delete.** Remove machine-local credentials (human-confirmed), clean fleet work dirs, mesh logout, mark the FLEET.md row retired.

## Decision rules
- **When** keys are missing → stop with the exact path template. Never ask the human to paste secrets into chat.
- **When** the machine is compromised → human decides on org token rotation; the provisioner does not rotate unilaterally.
- **When** provisioning for untrusted code → Sandbox tier, isolated machine, single-repo deploy key.
- **When** remote access is needed → enable only with explicit human password prompts.

## Red flags
- Credentials echoed to chat or written to git
- Personal Desktop paths as a required input
- Production app deployed during provision
- OAuth tokens shared across machines via cloud sync
- "Verified" without command output
