# Open-Source Release Pipeline (depth reference)

> Load this file when ANY work turns private/client/internal code into a public
> repository: open-sourcing a tool, publishing one of the owner's own projects, or shipping
> a sanitized client deliverable. This is a release/sanitization pipeline, NOT the
> deploy pipeline (CI/CD lives in SKILL.md) and NOT GitOps (`gitops-skill.md`). Those
> ship code to running environments; this one strips code clean and publishes it.
> Methodology absorbed 2026-06-14. No upstream source is vendored here.

**Source canon (verified 2026-06-14):** methodology lifted from the ECC project
(github.com/affaan-m/ECC, MIT) `opensource-pipeline` skill and its three staged agents
(`opensource-forker`, `opensource-sanitizer`, `opensource-packager`). Discipline only;
no ECC scripts, regex packs, or agent files are copied into the fleet. This is the
shape of a safe public-release pipeline, re-expressed for Solaris.

## When to reach for it

- A private repo, client deliverable, or internal tool needs to go public.
- The owner wants to open-source one of their own projects (the dev shop's tooling, a game
  utility, a CLI).
- Anyone is about to `gh repo create --public` from a codebase that has ever held a
  secret, an internal hostname, or a client name.

Do NOT use this for routine deploys (that is SKILL.md) or for shipping to a private
client environment (that is the deploy lane). The trigger is publication, not delivery.

## The model: three gates, never skip the middle one

The pipeline is three stages run in order. The second stage is an independent auditor
that distrusts the first. That separation is the entire safety value. Do not let the
same pass both transform and bless its own output.

| Stage | Verb | Role | Writes |
|---|---|---|---|
| 1. Fork | transform | Copy to staging, strip secrets, parameterize internal refs, fresh git history | `FORK_REPORT.md` |
| 2. Sanitize | verify | Independent read-only audit; PASS / FAIL / PASS-WITH-WARNINGS | `SANITIZATION_REPORT.md` |
| 3. Package | dress | License, README, CONTRIBUTING, setup script, AGENTS.md, issue templates | the public-facing files |

Staging layout (never publish from the original working tree):

```
$STAGING/<project>/
  FORK_REPORT.md
  SANITIZATION_REPORT.md
  AGENTS.md
  setup.sh
  README.md  LICENSE  CONTRIBUTING.md
  .env.example
  ... sanitized project files
```

---

## Stage 1: Fork (strip and parameterize)

Copy the source into a fresh staging directory, excluding generated and sensitive
trees, then strip secrets and replace internal references. Parameterize, do not
delete: every value pulled out gets a corresponding line in `.env.example` so the repo
still runs.

Exclude on copy: `.git`, `node_modules`, `__pycache__`, `.venv`/`venv`, `.env*`,
`*.pyc`, `.the coding agent/`, `.secrets/`, `secrets/`, `sessions/`, `dist/`, build output.

**Always remove (never publish):** `.env` and every variant, `*.pem` `*.key` `*.p12`
`*.pfx` `*.jks`, `credentials.json` / `service-account*.json`, `.secrets/`,
`.the coding agent/settings.json`, `sessions/`, and `*.map` source maps (they leak original file
paths and structure).

**Strip content from, do not remove:** `docker-compose.yml`, `config/`, `nginx.conf` -
replace hardcoded values with `${VAR_NAME}` and add the var to `.env.example`.

### Secret detection surface (what to scan for)

Treat any match as a secret to extract. Maintain the regex pack in the sanitizer
(below); the same surface drives both stages. Cover at minimum:

- Generic `*KEY/TOKEN/SECRET/PASSWORD/API_KEY/AUTH* = <16+ chars>`
- AWS access keys `AKIA[0-9A-Z]{16}` and `aws_secret_access_key` values
- Database URLs with embedded creds: `(postgres|mysql|mongodb|redis)://user:pass@host`
- JWTs (three base64 segments `eyJ....eyJ....`)
- Private keys `-----BEGIN ... PRIVATE KEY-----`
- GitHub tokens `gh[pousr]_...` and `github_pat_...`
- Google OAuth `GOCSPX-...` and `...apps.googleusercontent.com`
- Slack webhooks `https://hooks.slack.com/services/T.../B.../...`
- SendGrid `SG.<22>.<43>`, Mailgun `key-<32>`
- High-entropy `^[A-Z_]+=<32+ chars>$` as a WARNING (manual review, never auto-strip
  on heuristic alone - false-positive risk)

### Internal reference replacement

| Pattern | Replacement |
|---|---|
| Internal/custom domains | `your-domain.com` |
| Home paths `/home/<user>/`, `/Users/<name>/` | `/home/user/` or `$HOME/` |
| Secret-file refs `~/.secrets/` | `.env` |
| Private IPs `192.168.*`, `10.*`, `172.16-31.*` | `your-server-ip` |
| Personal emails | `you@your-domain.com` |
| Internal org / client names | generic placeholder + `.env` var |

### Git history is part of the secret surface

A clean working tree with a dirty history still leaks. Reset history to a single
initial commit in staging:

```
cd $STAGING/<project> && git init && git add -A
git commit -m "Initial open-source release"
```

If the requirement is to keep history (rare), rewrite it with a history scrubber
(`git filter-repo`, BFG) and re-audit every commit - do not ship raw history off a
repo that ever held a secret. Default to fresh history.

Stage 1 ends with `FORK_REPORT.md`: files removed, secrets extracted to `.env.example`,
internal refs replaced (with counts), and any items flagged for manual review.

---

## Stage 2: Sanitize (independent verify, read-only)

A separate auditing pass that trusts nothing from Stage 1. Read-only: it generates a
report, it never edits. Be paranoid - false positives are acceptable, false negatives
are not. **A single CRITICAL finding in any category = overall FAIL.**

Six scan categories:

1. **Secrets** (CRITICAL) - re-run the full regex surface above on every text file.
2. **PII** (CRITICAL) - personal emails (gmail/yahoo/icloud/etc.), private IPs not
   documented as placeholders, `ssh user@ip` strings.
3. **Internal references** (CRITICAL) - leftover home paths, `.secrets/` refs, client
   names, internal hostnames.
4. **Dangerous files** (CRITICAL - existence alone fails) - any `.env*`, `*.pem/key/
   p12/pfx/jks`, `credentials.json`, `.secrets/`, `.the coding agent/settings.json`, `sessions/`,
   `*.map`, vendored `node_modules/`.
5. **Config completeness** (WARNING) - `.env.example` exists and covers every env var
   referenced in code; `docker-compose.yml` uses `${VAR}` not literals.
6. **Git history audit** - `git log --oneline | wc -l` should be 1; grep history for
   `password|secret|api.?key|token`.

Verdict rules:
- Any CRITICAL finding -> **FAIL**. Fix in Stage 1, re-run Stage 2. Cap at 3 auto-retry
  cycles, then hand the findings to a human.
- Warnings only -> **PASS WITH WARNINGS** (publisher decides).
- Clean -> **PASS**, proceed to packaging.

Report rule: never print a full secret value - truncate to first 4 chars + `...`.
Output is `SANITIZATION_REPORT.md` with the per-category table and verdict.

---

## Stage 3: Package (make it usable)

Only runs after PASS or PASS-WITH-WARNINGS. Goal: a stranger can clone, run one script,
and be productive - including with a coding agent.

Generate (verify every command against the actual project - wrong commands are worse
than none):

- **AGENTS.md** - the most important file. Under 100 lines: what it does, copy-pasteable
  quick-start + command list, an architecture tree that fits a terminal, the real key
  files, the env-var table from `.env.example`. List files that exist, not hypothetical
  ones.
- **setup.sh** - one-command bootstrap, `set -euo pipefail`, prereq checks with clear
  errors, copies `.env.example` -> `.env`, installs deps. `chmod +x` it.
- **README.md** - enhance if a good one exists, do not clobber. Add a "Using with
  a coding agent" section. Link to AGENTS.md rather than duplicating it.
- **LICENSE** - standard SPDX text for the chosen license; copyright = current year.
  Confirm the license is compatible with every dependency before publishing (see flag).
- **CONTRIBUTING.md** - setup, branch/PR flow, code style, issue guidelines.
- **.github/ISSUE_TEMPLATE/** - `bug_report.md` + `feature_request.md` when a GitHub
  repo is the target.

---

## Stage 4: Publish checklist (human gate before going public)

Never auto-publish. Walk this before `gh repo create --public`:

- [ ] `SANITIZATION_REPORT.md` verdict is PASS or PASS-WITH-WARNINGS, and every
      warning has been read and accepted.
- [ ] Publishing from the **staging** tree, not the original (history is fresh / clean).
- [ ] `git log --oneline | wc -l` matches the intended history (1 for fresh).
- [ ] `.env.example` present and complete; no real `.env` anywhere in the tree.
- [ ] LICENSE present and license-compatible with all dependencies.
- [ ] AGENTS.md / README commands actually run on a fresh clone.
- [ ] A CI workflow exists and pins every third-party action to a full commit SHA, not
      a floating tag (see SKILL.md CI template + `gitops-skill.md` section 6 on the 2026
      action-compromise pattern). A public repo's CI is itself a supply-chain surface.
- [ ] Owner (for own projects; the client's named approver for client code)
      has explicitly approved making it public.
- [ ] Repo created `--public` only on that approval; push; verify the live repo shows
      no `.env`, no secrets in the Actions logs, no internal hostnames.

---

## Fleet doctrine notes

- **No code bundling.** This file is methodology lifted from ECC (MIT). The regex packs,
  the ECC agent files, and the ECC pipeline scripts are NOT vendored into the fleet -
  re-implement the discipline natively if/when tooling is built.
- **SHA-pin CI.** Any CI shipped in a public release pins actions to commit SHAs. A
  public repo invites forks and PRs; floating tags are a live supply-chain hole.
- **Memory scope keys.** When recording outcomes of a release run, scope memory under
  `devops/opensource-release/<project>` so per-project sanitization verdicts and
  publish decisions stay isolated and auditable, never blended across projects or
  clients.
- **License compatibility is load-bearing.** Confirm the chosen LICENSE is compatible
  with every dependency's license before publishing. Weak-copyleft and GPL deps can
  constrain what license the released repo may carry.

## Cross-references

- `SKILL.md` - the deploy CI/CD pipeline + the supply-chain SHA-pin CI template.
- `gitops-skill.md` section 6 - the 2026 third-party-action compromise warning.
- `rules.md` - the hard red flag: never publish unsanitized client code or secret-
  bearing git history.
- Org security pass: see the security-auditor employee for deeper secret-scanning tooling.
