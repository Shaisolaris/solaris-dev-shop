# Headless Fleet Runbook - Mac Mini a coding agent Build Machines

INTERNAL Solaris ops doctrine. Fleet = headless Mac minis running a coding agent as build workers.
The owner dispatches from HQ. Load per SKILL.md reference table when running multi-machine builds.
> ⚠️ SOURCE OF TRUTH = `Control/FLEET.md` DISPATCH PROCEDURE (field-proven). If this runbook and FLEET.md ever disagree, FLEET.md wins. Key field corrections (2026-07-15) baked in below.
>
> **SSH CHANNEL (critical):** Do NOT use tailscaled's built-in SSH on macOS - its pure-Go build cannot map macOS user accounts and every login fails "no such local user". Use plain OpenSSH to the machine's `.local` name (e.g. `ssh <YOUR_USER>@<YOUR_HOST>.local`) with HQ's key in the worker's `authorized_keys`. Tailscale provides the network reachability off-LAN; it does NOT provide the SSH login. Never ask the owner to approve a Tailscale SSH-check link.
> **the coding agent auth (critical):** GUI `the coding agent /login` stores creds in the macOS Keychain, which SSH-spawned streams CANNOT read. Use `the coding agent setup-token` once, save to machine-local `~/.solaris/the coding agent.token` (600), and have every stream launcher `export CLAUDE_CODE_OAUTH_TOKEN=$(cat ~/.solaris/the coding agent.token)`. Verify in stream context with `the coding agent -p "reply AUTH-OK"`.
> **Git white-label:** author = `the owner` + GitHub noreply address (never the coding agent, never real email); `includeCoAuthoredBy:false` in `<agent-config>/settings.json`. Reviewer greps `git log --format=%B` for the coding agent/co-authored/generated → must be empty before merge.


## 1. Machine provisioning (headless Mac mini)

1. Create a dedicated standard user `solaris-worker`. NOT admin. NOT the owner's personal account. No iCloud login.
2. Enable auto-login for that user: System Settings → Users & Groups → "Automatically log in as" → `solaris-worker`.
   Required so the machine comes back working after a power cut with no monitor attached.
3. Enable Remote Login (SSH): System Settings → General → Sharing → Remote Login → restrict to `solaris-worker`.
4. Enable Screen Sharing the same way. SSH is the primary channel; Screen Sharing is the break-glass GUI path
   (macOS auth dialogs, Settings toggles that have no CLI).
5. Set power to never-sleep:
   `sudo pmset -a sleep 0 displaysleep 0 disksleep 0 womp 1 autorestart 1`
   `autorestart 1` = auto power-on after power failure. Verify with `pmset -g`.
6. Install Tailscale and log the node in to the Solaris tailnet.
7. Name the node by role: `mini-01`, `mini-02`, `mini-sandbox`.
8. All HQ → mini access (SSH + Screen Sharing) goes over Tailscale. Never port-forward SSH on the LAN router.
9. Record the machine in the fleet inventory: hostname, Tailscale IP, macOS version, assigned repo(s).

## 2. a coding agent install + auth

1. Install Node via the official pkg installer. (Fleet exception to host-clean: minis ARE the build hosts.)
2. `npm install -g @anthropic-ai/the coding agent-code`
3. Auth: run `the coding agent setup-token` in the GUI session (the owner approves in browser once), save the printed token to `~/.solaris/the coding agent.token` (600, machine-local - never iCloud/.zshenv literals). Streams read it via the launcher export. GUI /login alone does NOT authenticate SSH streams (Keychain unreadable over SSH).
4. Set git identity per machine so commits are traceable:
   `git config --global user.name "mini-01"` / `user.email` = the Solaris bot address.
5. Git credentials: `gh auth login` (repo scope only) OR a per-machine SSH key:
   `ssh-keygen -t ed25519 -C "mini-01"`
6. Each machine gets its OWN deploy key, added to ONLY the repo it is assigned.
7. Never reuse a key across machines. Never add a machine's key to a second repo.
   Compromise blast radius = one machine, one repo.
8. Verify before dispatching work:
   - `the coding agent --version`
   - `gh auth status` or `ssh -T git@github.com`
   - test clone of the assigned repo.

## 3. Work-stream protocol

1. One stream = one module = one git branch: `stream/<module>` (e.g. `stream/auth-api`).
2. Never two streams in one branch. Never one stream spanning modules.
3. Launch every stream inside tmux, one session per stream, named after it:
   `tmux new -s stream-auth-api`
4. Streams survive SSH disconnects. Reattach from HQ: `tmux attach -t stream-auth-api`.
5. Launch via a `launcher.sh` that sets PATH + exports the the coding agent token, so tmux/SSH context has auth:
   `export PATH=/opt/homebrew/bin:$PATH; export CLAUDE_CODE_OAUTH_TOKEN=$(cat ~/.solaris/the coding agent.token); the coding agent -p "$(cat WORK-ORDER.md)" --allowedTools "Read,Write,Edit,Bash"`
6. Every stream starts from a `WORK-ORDER.md` at the stream branch root containing:
   - **Scope** - exactly what to build; the module boundary.
   - **Interface contracts** - function signatures / API shapes other streams depend on. Frozen.
   - **Definition of done** - tests passing, lint clean, docs updated, PR open.
   - **Forbidden files** - paths the stream must not touch (other modules, shared config, CI files unless the work order says so).
6. a coding agent works ONLY within the work order. Scope questions go back to HQ, never improvised.
7. When done: push `stream/<module>`, open a PR against main with the work order linked and test output pasted.
8. NEVER push to main. Branch protection on main enforces this. Treat any direct push as an incident.

## 4. Review flow

1. All PRs are reviewed from HQ: the owner (human) + the code-reviewer employee run the review pass.
2. Merge only after the review itself ends `Gate: passed`. No gate line, no merge.
3. The ONE-HUMAN-REVIEW CEILING is the fleet's throughput limit: streams produce PRs faster than one
   human can review them, so review-queue depth - not machine count - caps parallelism.
4. Do not spin up more streams than the review queue can drain.
   See project-manager's AI-fleet model for the capacity math.
5. Stale PRs (> 2 days unreviewed) pause their stream. The mini idles or takes the next work order
   rather than piling unreviewed diffs.

## 5. Safety rails

1. Minis hold ONLY: the assigned repo's code + the deploy key scoped to that repo. Nothing else.
2. NEVER on a mini: client credentials, brain repo access, payment/store keys
   (App Store Connect, Play Console, Stripe), Solaris-wide secrets, personal accounts.
3. Deploys that need real credentials run from HQ or CI. The mini's job ends at the PR.
4. Untrusted or inherited codebases (client handoffs, unknown provenance) run ONLY on the designated
   sandbox machine (`mini-sandbox`).
5. `mini-sandbox` holds no deploy keys at all and gets wiped between engagements.
6. If a mini is lost or compromised: revoke its deploy key and Tailscale node immediately (Section 7),
   rotate anything it could reach, audit the repo's recent pushes.

## 6. Health checks (daily)

1. Run `git fetch --all` on every active workspace. Confirms the deploy key still works and the clone is fresh.
   A fetch failure is a same-day fix.
2. Check disk: `df -h /`. Flag under 20 GB free - a coding agent caches, node_modules, and build artifacts
   eat disks silently.
3. Run `tmux ls` on each machine.
4. Post the tmux list + fetch/disk results to `STATUS.md` in the fleet inventory repo,
   one section per machine, dated.
5. Any machine failing two consecutive daily checks is pulled from dispatch until fixed.

## 7. Teardown (machine leaving the fleet or reassigned)

1. Revoke the deploy key from the repo: GitHub → Settings → Deploy keys → delete.
2. `gh auth logout` on the machine (or delete the SSH keypair).
3. Wipe the workspace: repo clone, `~/.the coding agent` session data, shell history, build artifacts.
4. For machine disposal or client-mandated wipes, erase the volume outright.
5. Remove the node from the Solaris tailnet.
6. Update fleet inventory + `STATUS.md` with teardown date and reason.
