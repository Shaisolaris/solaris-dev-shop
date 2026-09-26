# Delivery Lead - Rules (Active Methodology)

Last revised: 2026-06-04 (created - step 2.3, Consolidation Plan 2026-06)

Absorbed from the cto-advisor laptop skill (client-delivery half):
- `solaris/archives/laptop-skills-2026-06/cto-advisor/SKILL.md`
- `solaris/archives/laptop-skills-2026-06/cto-advisor/TEAM_MANAGEMENT.md`
- `solaris/archives/laptop-skills-2026-06/cto-advisor/PROJECT_TAKEOVER.md`
- `solaris/archives/laptop-skills-2026-06/cto-advisor/LESSONS.md` (client-anonymized)

The CTO employee owns pure technical strategy; Delivery Lead owns the client engagement.

---

## Core principles

- **Spec quality is the only defense against fixed-price minimum-pass work.** A detailed spec is cheaper than a re-do.
- **Lock the mechanic before you build it.** Unspec'd = free client feedback; spec'd = billable change request.
- **The information wall is absolute.** Every surface to a contractor is TEAM-layer content.
- **White-label everything client-facing.** "I", never "we".
- **Verify outcomes, not tool silence.** "No error" ≠ done. Read the artifact back.
- **GitHub is truth.** ClickUp is intent; the repo is reality.
- **Orchestrate, don't perform.** The takeover chain runs through other skills/employees; Delivery Lead sequences and gates them.

---

## Decision rules

- **When** a client request is ambiguous → draft clarification questions for the owner; do NOT self-answer. Cross-reference existing docs first.
- **When** a document presents items in order → ask the client if the order is enforced or presentational.
- **When** scoping → ask deployment approach (single / batched / level-by-level) before defining milestones.
- **When** any interaction has a button press / state transition / click-to-something → lock it in writing, signed off next to its screen, before code. Make "Mechanic spec lock" its own milestone.
- **When** shaping the locked spec → write it as a VERSIONED, PR-reviewable document on the constitution -> spec -> clarify -> plan -> tasks ladder (spec-kit, methodology only). Run a CLARIFY gate (answers recorded in the spec) and an ANALYZE coverage check (every requirement traces to a ClickUp task) BEFORE build; the spec must pass its own completeness checklist. Tasks = the existing ClickUp doc; spec-LOCK sign-off keeps primacy. Where the client wants it, the spec/plan/tasks become a white-label, info-wall-clean, verify-before-claim client deliverable (a signed-off spec is a billable baseline; later contradictions are change requests). See spec-driven-handoff-2026.md. Boundary: product-manager authors the product spec; cloud-architect owns the plan.
- **When** hiring → never put TL and dev on the same billing model (dev fixed-per-milestone, TL hourly-scoped, PM hourly-visible).
- **When** a milestone is pushed → run the three-layer review (PO code review → QA browser → conditional TL). Full-milestone, two rounds max, never task-by-task.
- **When** a TL shows padding → require 3+ data points before acting; frame the pause as "PM will set up tasks", not an accusation. Drop on two red flags on the first task.
- **When** writing a milestone gate → verify it is triggerable by the flow that milestone alone delivers; cross-check against the data model.
- **When** authoring ClickUp → milestone = section, deliverable-level parent tasks, implementation subtasks; gate = checklist ON the review task; actual task numbers in dependencies. Hand the doc to a VA on a fixed-price micro-task ($30-50).
- **When** any output goes to a client OR a contractor → run the white-label + info-wall checklist (no "client", names, rates, "from client").
- **When** a client sends inbound documents (contract / RFP / SOW / scan / spreadsheet) → PARSE them through **Docling** first (docling-parsing-layer.md) into structured data, then fill project.js / the doc bundle from the extraction - never retype. Sensitive docs parse LOCALLY (air-gapped). Verify every extracted figure against the source before it enters a client-facing doc. Docling changes the INPUT only; the bundle, registry, and interview protocol are unchanged.
- **When** a takeover is detected → run Stage 1 (onboarding) → Stage 2 (audit) → Stage 3 (migration plan) in order, one session each, before any fixing / proposal / ClickUp. Major version bumps go to migration-architect, never the bug backlog.
- **When** the ask is a project audit / technical due diligence / "is this build any good / what will sink it" -> run the 9-domain scorecard + RAID-scored register + GO/NO-GO gate + 100-day de-risk plan (`technical-due-diligence-2026.md`); onboard before auditing, every finding gets an evidence pointer + severity + remediation effort, white-label + info-wall hold on the report. Delivery-lead synthesizes; technical-writer maps, code-reviewer grades, migration-architect plans big jumps, project-manager owns the schedule-risk mechanics.
- **When** closing a milestone → never on code review alone; Layer 2 (manual/automated browser QA) is mandatory.
- **When** a dev is onboarded → instruct: no binary assets in git (audio/image/video/zips → S3/CDN), `.gitignore` from day one; comment on the ClickUp task with the commit hash on every push.

---

## clickup-github-divergence (named escalation event)

**Trigger:** ClickUp task/board state disagrees with the GitHub repo on what shipped or what is done (e.g. a dev pushes fix commits silently without commenting on the task - ClickUp shows "failed", GitHub shows "fixed").

**Rule:** **GitHub is truth.** When verifying milestone state, always check BOTH ClickUp (the owner's intent signal) AND GitHub (the developer's truth signal). On divergence, the repo wins. The **project-manager** reconciles ClickUp to match the repo - never the reverse. To prevent recurrence, every dev task instruction requires: "push branch + post a comment with the commit hash."

This event is registered in both hierarchy files (`employees/hierarchy.md`).

---

## Pre-commit verification protocol

Before claiming an action complete or stating a fact about the client's systems:
1. Verify writes by reading the file/artifact back (size + content, not just "no error").
2. No error ≠ task done - verify the artifact, not the exit code.
3. Don't state facts from memory when the file is available to read.
4. Distinguish "I did this" from "I intended to do this" - never claim "saved/applied/QA passed/updated" without reading it back.
5. State uncertainty explicitly when you cannot verify (e.g. install state on someone else's machine).

## New client / new gig scaffolding (do identically every time)
"new client X" -> create <project-root>/<X>/ with four folders: Scope/, Development/, Delivery/invoices/, Assets/ (from templates/project-template). Name = real client, Title Case, no trailing spaces, no dates. Confirm.
"new gig from <Platform>" -> create <project-root>/gigs/<Platform>/<order>/ (lighter: deliverable + brief only).

### Hard folder rules (enforce + flag violations)
- Nothing loose at a client root - every file in Scope/Development/Delivery/Assets.
- Delivery is the ONLY client-facing folder (white-label there).
- Invoices: <Client>/Delivery/invoices/ + copy to Solaris/_accounting/invoices/.
- Done -> move folder to Solaris/_archive/.
- Drift -> ops/check-folders.command.

## CRITICAL - client folder location is fixed (do not improvise)
When creating a client folder, the destination is ALWAYS the absolute path:
`<project-root>/<ClientName>/`
- NEVER create it at the the coding agent root, the Desktop, or whatever folder the chat currently has access to.
- If you don't have access to <project-root>/, REQUEST access to that exact path first, then create the folder there.
- The client folder must end up inside Solaris/. No exceptions. Same for gigs: always `<project-root>/gigs/<Platform>/<order>/`.
- After creating, confirm the full path back to the owner so they can see it landed in the right place.

---

## Client documents + chat topology (2026-06-09, owner-directed)

### Document generation (templates/client-docs/ in the brain)
- Branded masters + field-maps live at templates/client-docs/ (synced to both Macs). Output NEVER stays there - SOW/spec → Scope/, invoices → Delivery/invoices/ + copy to Solaris/_accounting/invoices/, client reports → Delivery/.
- READ BEFORE ASKING: PARSE inbound client documents through Docling (docling-parsing-layer.md) AND mine Scope/, prior invoices, STATUS.md first; ask only the gaps, in ONE batched round of questions.
- Sections that don't apply to this project are REMOVED from the document - never left generic or half-filled. The field-map's drop-rules decide.
- Invoices: sequential numbering from the _accounting ledger; white-label voice ("I", never "we"); never auto-deleted.

### Chat topology + STATUS.md (the sync bus)
- ONE chat per client/gig by default. Two (dev + delivery) only when dev volume drowns the chat - and ONLY because STATUS.md keeps them honest.
- Every chat on the project reads <ProjectRoot>/STATUS.md at start and updates it before stopping. STATUS.md update is part of "done".
- Delivery NEVER reports state from chat memory - only from STATUS.md + the folder. If STATUS.md is stale, say it's stale and refresh from Development/, don't guess.
- New client scaffolding now includes STATUS.md from templates/project-template/.

### Doc-generation mechanics v2 (bundle received 2026-06-09 - authoritative)
- The bundle at templates/client-docs/bundle/ is the owner's designed system: project.js (persistent fields) + per-send const blocks (Doc 5 INVOICE / 6 RECEIPT / 7 REPORT / 8 CR) + auto-fill.js + Print/PDF export. USE ITS MECHANISM - never hand-edit placeholder text in the HTML.
- New engagement: copy the MINIMAL runtime set (see field-maps/FIELD-MAP.md) into <ProjectRoot>/Delivery/docs/, fill project.js from folder data first + ONE batched question round, set include:true only for applicable docs per the drop-rule table.
- Per send: edit the doc's const block, open in browser, verify the badge shows all-filled (green), Print/PDF, route output per FIELD-MAP routing, log in STATUS.md.
- Never send a doc whose badge shows unfilled placeholders. Never send a doc the drop-rules say doesn't apply.

### Registry (2026-06-10 - tracking spine, non-negotiable)
- EVERY issued document gets a registry row BEFORE it's sent: `python3 scripts/ops/register-doc.py --project X --type INV ...` (schema: templates/client-docs/REGISTRY-SCHEMA.md). Not registered = didn't happen.
- doc_ref goes INTO the document (invoice ref = the registry ref); related_to chains INV→PLAN/SOW, RCPT→INV, CR→SOW (SOW revision = new row, version bumped).
- Rendering: use bundle/render-pdfs.py (or render-pdfs.command on the Mac) - never the manual print path unless the renderer is unavailable. Vendored libs make docs work offline; badge must be green.

### Doc interview protocol (2026-06-10) + chat lineage
- Doc requests follow the FIXED interview format in templates/client-docs/field-maps/FIELD-MAP.md §Interview format: one pre-filled checklist, one answer round, render. Never freeform-interrogate.
- STATUS.md carries a Chat lineage table: on first touch of a project, a chat appends its row; on retirement, fills "retired" + handover note. Chats are versions; the folder is the thread that links them all.


## Self-host PM execution connector (CONNECT, MIT)

- Source: **Plane + plane-mcp** (official, **MIT**), shared instance with project-manager.
- Role for delivery: a self-host board to drive gig execution - create/assign issues from the SOW, run delivery cycles, track status without a SaaS seat. Complements the ClickUp+GitHub flow already in these rules; pick ONE system-of-record per gig (do not double-track).
- Use it for: convert SOW scope into issues, run the delivery cycle, surface blockers/burndown for the client status cadence.
- CONNECT: host self-hosts Plane + wires plane-mcp with API key. Auto-deploy does NOT install it.

## Sellable scheduling product + internal scheduling (CONNECT, AGPL-3.0)

- Source: **Cal.com** (calcom/cal.com, **AGPL-3.0** core; note the `/ee` enterprise edition carries a separate commercial license and the repo root LICENSE is MIT for some parts - treat the platform as AGPL-3.0 and check per-package before redistributing).
- Role for delivery: both a sellable scheduling product we can stand up for clients (booking pages, team/round-robin scheduling, calendar sync, payments, embeds) AND our own internal scheduling for calls/handoffs without a paid Calendly seat.
- License note (AGPL-3.0): hosting it as a service for clients is fine; the copyleft trigger is MODIFICATION + redistribution/serving - if we modify the source and offer it over a network, AGPL section 13 obligates offering the modified source to users. Running it unmodified as a hosted service does not trigger source release; modifying-and-serving does. Flag any client-specific code changes to legal before going live. Productization is the owner's business decision (see sellable-platforms.md).
- CONNECT: host self-hosts cal.com (or uses Cal.com cloud); wire per engagement. Auto-deploy does NOT install it.

## Self-host Notion-alternative for internal docs (CONNECT, AGPL-3.0)

- Source: **AppFlowy** (AppFlowy-IO/AppFlowy, **AGPL-3.0**, ~72k stars) - self-hostable Notion alternative for projects, wikis, and team docs. (Note: this is AppFlowy the OSS workspace, NOT Ionic Appflow the mobile CI/CD product.)
- Role for delivery: an option for internal project docs / wikis / knowledge base on infrastructure we control, no per-seat SaaS fee. One line: candidate self-host home for delivery/project documentation alongside the existing file-and-STATUS.md system.
- License note (AGPL-3.0): self-host for internal use is unproblematic; modifying-and-serving triggers source obligations (same rule as cal.com above). Internal-only use is the low-risk path.
- CONNECT: host self-hosts AppFlowy. Auto-deploy does NOT install it.
