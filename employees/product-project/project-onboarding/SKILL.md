---
name: project-onboarding
description: Runs the Solaris project activation sequence. Fires when Shai says "new project", "project activated", "onboard this project/client", "moving this into Solaris", "set up the project", or when a client project first gets its Solaris folder. One short guided intake, then full automated setup - folders, deploy model, credentials sheet, repo, branches, workflows, registry - so project starts cost Shai near-zero thought.
---

# Project Onboarding

This employee activates a client project into Solaris Dev Shop. Ask ONLY the short intake below (plain chat, never MCQ widgets), then set up everything. Skills: open every response per the skills-mention law.

**Step 0 - Read rules of the land first: Control/FLEET.md (deploy doctrine + activation questions) and meta/chief-of-staff/references/company-facts.md. Skipping = gate failure.**

## WORKING FOLDER LAW (hard rule, step zero of every onboarding)
Create <project-root>/<Client>/<Project>/ with STATUS.md + ROUND-PLAN.md + HANDOVER.md stubs BEFORE anything else, announce the path in chat, and instruct: every future chat for this project points HERE first and reads STATUS.md. Chat memory NEVER lands in app-internal session folders - the folder must be movable to another machine and picked up by a fresh chat with zero loss.

## The intake (30 seconds, defaults in brackets - silence accepts defaults)
1. Project type? web app / website / mobile app / desktop app / game / other
2. Deploy model? [web: main=live, dev=staging, both cost money | mobile/desktop/game: nothing auto-deploys; main=release-candidate; store/installer submission = Shai-approved step | none]
3. Client name + which credentials exist or are needed (hosting, domain, stores, DBs, APIs)?
4. Budget/timeline anchors worth recording?

## Automated setup (execute ALL, verify each with real output)
1. FOLDERS: Solaris/<Client>/ with exactly Scope, Development, Delivery, Assets + STATUS.md carrying: the STANDING ORDER block, DEPLOY-MODEL line (from intake), stage, client identity/commercial terms (internal only).
2. CREDENTIALS: locate the client-credentials workbook (search the project credential index for *credential*; known org artifact). Append one row per credential from intake: client, system, username, where-the-secret-lives (NEVER store secret values in the sheet or chat - reference keychain/keys-folder locations). Confirm row count written.
3. REPO (if code project): create/verify GitHub repo (fleet token), create integration branch, install the 3 fleet workflows from scripts/ops/event-driven/, set CLAUDE_CODE_OAUTH_TOKEN secret, protect nothing on integration, note main/dev = Shai-only per deploy model.
4. REGISTRY: if any money documents will exist, confirm registry numbering (Solaris/_accounting/registry) is reachable.
5. PLAN SKELETON: Scope/ gets an empty ROUND-PLAN.md header + the project brief; write the DEPLOY-MODEL into FLEET-relevant notes.
6. Report to Shai in 5 lines: folder path, deploy model recorded, credentials rows added, repo+workflows state, what is missing and needs him (only genuinely-his items).

## SELF-QA GATE (before replying - mandatory)
1. Intake asked in plain chat, defaults honored, no MCQ widget?
2. All four folders + STATUS with STANDING ORDER + DEPLOY-MODEL exist on disk (listed)?
3. Credentials rows appended and counted - zero secret VALUES stored anywhere?
4. Repo/branches/workflows/secret verified with real command output (code projects)?
5. White-label law respected in every artifact?
6. Report is 5 lines, only Shai-owned gaps escalated?
FINAL CHECK - Response opens with "Skills: <invoked>". Any check fails - fix first. End with the literal line: Gate: passed


## QA LOOP (GOSPEL - meta/QA-LOOP-GOSPEL.md, non-negotiable)
Any deliverable this skill produces that is mechanically checkable (code, HTML/JS, scripts, configs, structured docs, spreadsheets, PDFs) MUST pass the Solaris Dev Shop QA loop before it ships: build → independent review → fix → repeat until the review is clean on the final artifact. No self-certification. Verify each finding against the actual artifact. Judgment deliverables (proposals, client messages) get an independent review against the owner's rubric. Log findings to qa-ledger.jsonl. Shipping without the loop is a process violation. Do not name a model vendor as the employee.
