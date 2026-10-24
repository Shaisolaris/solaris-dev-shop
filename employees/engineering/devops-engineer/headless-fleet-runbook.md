# Headless Fleet Runbook - Dedicated Build Workers

Fleet workers run the project's selected coding agent on explicitly assigned repositories.
The project-local fleet inventory and authorized work order define the selected machine,
repository, branch, permitted operations, authentication scope, isolation and teardown.
If those records conflict, stop the affected dispatch and reconcile them with the owner;
a private control file or this example cannot expand the grant.

Use the owner's approved remote-access channel. Verify the host identity and restrict
access to the dedicated worker account. Do not append HQ keys, enable remote services,
forward an SSH agent or approve a new access grant merely because this guide is loaded.
Use the provider's current supported headless authentication for that account; GUI and
SSH credential availability must be tested in the actual launch context rather than
assumed. Preserve accurate commit authorship and any required assistance disclosures.

This is an optional operator-run provisioning runbook for an explicitly selected,
owned worker. Loading an employee does not execute these steps. Do not enable SSH,
Screen Sharing, never-sleep/restart settings, remote agents or scheduled health
checks as part of routine skill loading. Confirm the existing work order covers
these services and their access/teardown before provisioning; keep unrelated host
settings unchanged. The daily checks below are a manual cadence unless the owner
separately requests a bounded schedule.

## 1. Machine provisioning (headless Mac mini)

1. Create a dedicated standard user `solaris-worker`. NOT admin. NOT the owner's personal account. No iCloud login.
2. Keep login and disk-encryption protections enabled. Do not enable automatic login as the default
   recovery mechanism for a machine holding source or credentials. Plan owner-assisted unlock after
   a power loss, or use an explicitly approved headless host design with equivalent access protection.
3. Use an existing approved remote-access service restricted to `solaris-worker`. If SSH must be
   enabled, the work order must cover that service, permitted callers and revocation. Verify the
   host key through the owner's trusted inventory before connecting; never suppress verification.
4. Screen Sharing is optional break-glass access. Enable it only when separately covered by the
   work order, with the selected account and private network boundary recorded.
5. Inspect power settings with `pmset -g`. Change only the selected machine's approved settings;
   continuous operation and power-failure recovery need an explicit decision that preserves disk
   encryption and owner-assisted unlock. Do not apply a blanket never-sleep recipe to other hosts.
6. Use the approved private network route. Adding a node or changing network access is a separate
   provisioning action, not an automatic consequence of loading a skill.
7. Name the node by role: `mini-01`, `mini-02`, `mini-sandbox`.
8. Do not expose SSH or Screen Sharing through router port forwarding. Verify effective reachability
   from permitted and excluded callers using the selected network's supported controls.
9. Record non-secret inventory: hostname, private address, OS version, assigned repositories,
   access owner, permitted operations and revocation procedure.

## 2. Coding agent installation and authentication

1. Identify the selected provider, official distribution, executable and required runtime in the
   work order. Install only those dependencies on the selected build host; no package is installed
   when this guide is read. Verify the executable's version against the official source.
2. Use the provider's supported headless sign-in or short-lived credential mechanism on the dedicated
   worker account. Do not copy a personal HQ session, persist a provider token in a shared shell
   startup file, or add a universal token export to every stream launcher.
3. Prefer the supported OS credential store or secret broker. If a provider requires a process
   environment credential, inject it only into that approved process, keep it out of command lines,
   logs and child test processes, and record its non-secret scope, expiry and revocation owner.
   If the actual SSH/tmux launch context cannot authenticate safely, hold that stream for the
   provider's supported owner-assisted approval instead of inventing a token-file workaround.
4. Set Git identity locally in each assigned repository using the approved worker identity and
   contact address. Keep authorship and required assistance disclosures accurate; do not erase
   provenance or suppress co-author information to make review pass.
5. Git credentials: do not run the owner's account-wide `gh auth login` on a worker. OAuth's `repo`
   scope is not a single-repository limit; it can grant access across the account's private repositories.
   Prefer a short-lived GitHub App installation token issued by HQ with the assigned repository and
   minimum permissions explicitly selected. Keep the App's signing key on HQ/the trusted issuer.
6. Fetch-only workers may instead use a dedicated, read-only SSH deploy key added to only the assigned
   repository. Do not reuse keys across machines or repositories, and do not forward HQ's SSH agent.
   Write-enabled deploy keys have broad Git authority within that repository; enable writes only when
   the work order requires them and verify the repository's actual branch protections.
7. Record the allowed repository, operations and expiry/revocation procedure from the grant metadata,
   without the secret value. If a deploy key cannot create a PR through the API, HQ creates the PR or
   supplies a separately scoped, short-lived installation token; do not fall back to broad OAuth.
   The one-repository blast-radius claim depends on this real configuration, not on a work-order file.
8. Verify before dispatching work:
   - the configured agent executable's reported version and successful supported authentication
     in the actual worker launch context, without printing credentials
   - the issuer's repository/permission/expiry metadata, or the deploy key's repository and read/write setting
   - a test fetch of the assigned repository; authentication success alone does not prove narrow scope.

References: [OAuth scopes](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps),
[deploy-key scope and limitations](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys),
and [installation token repository/permission selection](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/authenticating-as-a-github-app-installation).

## 3. Work-stream protocol

1. One stream = one module = one git branch: `stream/<module>` (e.g. `stream/auth-api`).
2. Never two streams in one branch. Never one stream spanning modules.
3. Launch every stream inside tmux, one session per stream, named after it:
   `tmux new -s stream-auth-api`
4. Streams survive SSH disconnects. Reattach from HQ: `tmux attach -t stream-auth-api`.
5. Launch the configured agent from a project-owned launcher that selects the assigned checkout,
   branch and bounded tool permissions. Use the provider's supported authentication reference;
   do not embed a token or unrestricted shell allowlist in this runbook. tmux preserves a process
   across disconnects but provides neither filesystem nor network isolation.
6. Every stream starts from a `WORK-ORDER.md` at the stream branch root containing:
   - **Scope** - exactly what to build; assigned repository and branch; permitted operations.
   - **Interface contracts** - function signatures / API shapes other streams depend on. Frozen.
   - **Definition of done** - named tests, lint, documentation and the required review artifact.
   - **Boundaries** - permitted paths, excluded data, filesystem/network isolation, resource limits,
     credentials available to the agent and how they are withheld from untrusted tests.
   - **Recovery** - checkpoint location, stop conditions, access expiry and cleanup owner.
7. A work order and tool allowlist describe policy; they do not enforce isolation. Run untrusted
   code in a separate credential-free sandbox. Verify the effective mount, network and credential
   boundaries before execution; do not assume forbidden-file prose prevents access.
8. Work only within the work order. Resolve scope conflicts with HQ; do not broaden permissions.
9. When authorized, push the assigned review branch and open a PR against the agreed base with
   the work order and exact revision/test evidence. Otherwise return the local commit for HQ to push.
10. Never push directly to the default or release branch. Verify the repository's actual protections
    and token permissions; branch protection must not be assumed from this guide. A direct push
    outside the work order is an incident.

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

1. Workers hold only the assigned source and explicitly approved, narrowly scoped agent/repository
   authentication. Keep provider credentials out of test subprocesses and untrusted sandboxes.
2. NEVER on a mini: client credentials, brain repo access, payment/store keys
   (App Store Connect, Play Console, Stripe), Solaris-wide secrets, personal accounts.
3. Deploys that need real credentials run from HQ or CI. The mini's job ends at the PR.
4. Untrusted or inherited codebases (client handoffs, unknown provenance) run ONLY on the designated
   sandbox machine (`mini-sandbox`).
5. `mini-sandbox` holds no provider or repository credentials. Recreate its disposable environment
   between engagements under the recorded cleanup scope; do not erase unrelated host data.
6. If a worker is lost or compromised: revoke its scoped repository/provider grants and remote-access
   identity (Section 7), rotate reachable credentials and audit recent repository operations.

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

1. Revoke the specific worker's repository grant or deploy key and its provider credential through
   the respective issuer. Verify revocation; do not log out unrelated accounts or revoke other workers.
2. Stop the assigned agent/tmux processes and remove only the documented worker credential-store
   entries. Never print the secret during verification or copy it into teardown evidence.
3. Remove the assigned workspace, caches and session artifacts according to the project's retention
   and recovery policy. Preserve required evidence and unrelated checkouts, history and account data.
4. Full-volume erasure is a separate destructive disposal action requiring the owner's explicit scope
   and approval; it is never an automatic reassignment step.
5. Remove the selected worker's remote-access/network identity if it is no longer required.
6. Update fleet inventory and `STATUS.md` with the date, grant identifiers (not secrets), verified
   revocations, retained evidence, cleanup scope and reason.
