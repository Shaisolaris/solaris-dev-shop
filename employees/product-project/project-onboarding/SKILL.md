---
name: project-onboarding
description: Runs a local project activation sequence. Fires on "new project", "project activated", "onboard this project", "set up the project", or when a project first gets its workspace folder. One short plain-chat intake, then a conservative local setup with activate.py - folders, STATUS.md with the recorded deploy model, credential locations, round plan, and a read-only Git check - that preserves existing owner files and resumes after interruption. Never deploys, stores secrets or changes CI.
---

# Project Onboarding

This employee activates a project workspace on the local machine. Ask the short intake below in plain chat, then run `activate.py`. Everything outside the project folder, and every live or account action, stays with the owner.

## Step 0 - Read the local project doctrine first
If the workspace has a project doctrine file (e.g. `project/FLEET.md`, `project/DOCTRINE.md`, or a company-facts reference), read it before the intake. Skipping a present doctrine = gate failure.

## The intake (plain chat, no defaults are assumed)
1. Project type? web app / website / mobile app / desktop app / game / other
2. Deploy model? Record the owner's words exactly. If there is no answer, it stays `UNRESOLVED`; silence never means `main=live` or any other default.
3. Project/client name, and which credentials exist or are needed: system, username and where the secret lives (vault or keychain location). Never ask for or accept the secret itself.
4. One-line brief (budget or timeline anchors may go here).

## Local setup (run it, then read its output)
Needs Python 3.12 (the supported interpreter); standard library only.
```bash
python3 employees/product-project/project-onboarding/activate.py activate <project-root> \
  --name "Client portal" --type "web app" [--deploy-model "<owner's answer>"] \
  [--brief "..."] [--credential "system=github;username=bot;location=1Password/Eng/GitHub"] \
  [--code] [--init-git] [--within <allowed-parent>] [--dry-run] [--json]
python3 employees/product-project/project-onboarding/activate.py resume <project-root>
```
- Creates `Scope/`, `Development/`, `Delivery/`, `Assets/`, `STATUS.md` (brief + `DEPLOY-MODEL:` line), `Scope/ROUND-PLAN.md` and `Delivery/CREDENTIALS.md` (locations only), plus the journal `.solaris-activation.json`.
- Existing owner files are never overwritten: a file activation did not write is kept and reported as `conflict_preserved`. Files it wrote earlier are updated when the intake changes, and every change is listed in `intake_changes`.
- Symlinks, dangling links or non-directories at controlled paths, an unreadable or too-deeply-nested journal or lock, or a root that is a file stop the run before any write (`blocked`) with a short message (no traceback).
- Secret-shaped input, unpaired surrogates, unknown credential fields (such as `notes`), multi-line fields and a root outside `--within` are refused with no writes (`invalid`). Detection is pattern-based and cannot prove text is secret-free.
- If a write fails, the files already written stay and the journal records progress; fix the cause and run `resume`. An identical rerun changes nothing. Temp files a killed run left next to its own targets (`.<file>.<hex>.activation-tmp`) are removed by the next run and listed in `removed_temp_files`.
- The journal is bound to its folder. A journal copied from another project (alone or with the folder) passes nothing on: the run reports it as a gap and the deploy model stays `UNRESOLVED` until stated again, and `resume` is refused there. In the same folder, an omitted answer is carried over and the report says so (`carried over ... not restated`).
- A deploy answer that is blank, made only of invisible or blank-looking characters (zero-width, BOM, Hangul/braille fillers, combining marks alone), or the word `UNRESOLVED` (including after NFKC or with those marks stripped) is no answer. `DEPLOY-MODEL:` text is accepted only in the deploy field. A brief may name a commit id (`commit`/`fork`/`sha` + 40 or 64 hex).
- The parent folder of `<project-root>` must already exist (a typo never creates a deep tree). One run at a time per project: a second concurrent run is `blocked` by `.solaris-activation.lock`; if a run was killed, the message says the lock is stale and the owner deletes it.
- Git (with `--code`): an existing repository is inspected read-only (branch, head, unborn). Activation never commits, stages, branches or touches the index. `--init-git` runs `git init` only where no `.git` exists and the root is not inside another repository; the first commit stays an owner step.
- Never performed: deployment, CI workflows or secrets, branch protection, remote repository creation, store submission, network calls.

## OUTPUT CONTRACT
1. **Intake record** - the answers as given; unanswered items named, not defaulted.
2. **Folder tree** - from the tool's `folders` and `artifacts`, with `conflict_preserved` items called out.
3. **Credential sheet** - row count from the result; locations only.
4. **Repo state** - the tool's `git` block, verbatim state (`skipped`, `absent`, `existing`, `invalid`, `not_inspected`, `initialized_unborn`, `inside_other_repository`).
5. **5-line report** - the tool prints it: path and status, deploy model, credential rows, repo state, what needs a human.

## SELF-QA GATE (before replying - mandatory)
1. Intake asked in plain chat, and no answer was replaced by a default?
2. `activate.py` actually ran and its status is quoted (`complete`, `partial`, `blocked`, `failed` or `invalid`)?
3. Every `conflict_preserved`, gap and error from the result is in the report?
4. No secret value appears in chat, intake or files; credential rows are locations only?
5. Nothing deployed, pushed, committed or configured remotely, and those steps are listed as owner-approved?

Any check fails - fix first. End with the literal line: `Gate: passed`
