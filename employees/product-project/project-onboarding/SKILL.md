---
name: project-onboarding
description: Runs a project activation sequence. Fires on "new project", "project activated", "onboard this project", "set up the project", or when a project first gets its workspace folder. One short guided intake, then automated setup - folders, deploy model, credential references, repo, branches, status docs - so project starts cost near-zero thought.
---

# Project Onboarding

This employee activates a new project into the workspace. Ask ONLY the short intake below (plain chat, never MCQ widgets), then set up everything.

## Step 0 - Read the local project doctrine first
If the workspace has a project doctrine file (e.g. `project/FLEET.md`, `project/DOCTRINE.md`, or a company-facts reference), read it before the intake. Skipping a present doctrine = gate failure.

## The intake (30 seconds, defaults in brackets - silence accepts defaults)
1. Project type? web app / website / mobile app / desktop app / game / other
2. Deploy model? [web: main=live, dev=staging | mobile/desktop/game: nothing auto-deploys; main=release-candidate; store/installer submission = human-approved step | none]
3. Project/client name + which credentials exist or are needed (hosting, domain, stores, DBs, APIs)?
4. Budget/timeline anchors worth recording?

## Automated setup (execute ALL, verify each with real output)
1. FOLDERS: `<project-root>/` with exactly `Scope/`, `Development/`, `Delivery/`, `Assets/` + `STATUS.md` carrying: the project brief, DEPLOY-MODEL line (from intake), stage, and client/commercial terms if any.
2. CREDENTIALS: create or update the project's credential reference sheet (one row per credential from intake: system, username, where-the-secret-lives). NEVER store secret values in the sheet or chat - reference keychain/secret-manager locations. Confirm row count written.
3. REPO (if code project): create/verify the git repo, create an integration branch, install CI workflows, set CI secrets from the secret manager, protect main per the deploy model.
4. PLAN SKELETON: `Scope/` gets a `ROUND-PLAN.md` header + the project brief; write the DEPLOY-MODEL into the project notes.
5. Report in 5 lines: folder path, deploy model recorded, credential rows added, repo+workflows state, what is missing and needs a human (only genuinely-human items).

## OUTPUT CONTRACT

Every activation deliverable uses this shape:

1. **Intake record** - the 4 answers (or defaults accepted) as given.
2. **Folder tree** - project root + Scope/Development/Delivery/Assets + STATUS.md with DEPLOY-MODEL.
3. **Credential sheet** - rows added, count confirmed, zero secret values.
4. **Repo state** - repo URL, integration branch, CI workflows installed (code projects).
5. **5-line report** - path, deploy model, credential rows, repo state, human-owned gaps.

## SELF-QA GATE (before replying - mandatory)
1. Intake asked in plain chat, defaults honored, no MCQ widget?
2. All four folders + STATUS with DEPLOY-MODEL exist on disk (listed)?
3. Credential rows appended and counted - zero secret VALUES stored anywhere?
4. Repo/branches/workflows/secrets verified with real command output (code projects)?
5. Report is 5 lines, only human-owned gaps escalated?

Any check fails - fix first. End with the literal line: `Gate: passed`
