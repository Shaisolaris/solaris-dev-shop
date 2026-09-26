# Delivery Lead - Learnings

```
Format: - **<YYYY-MM-DD> - <anonymized context>**: <what happened> *Proposed rule: <general takeaway>* Tags: [#scoping], [#spec-lock], [#api], [#docs], [#team], [#clientcomms], [#process], [#clickup], [#promoted?]
```

**ANONYMIZATION RULE:** No client identifiers, screen names, tag numbers, or contractor names enter this file. Generalize to "a client project". The rule is the lesson; the raw client-specific example stays in that client's project folder.

---

## Pending observations (client-anonymized from cto-advisor LESSONS.md, 2026-06-04)

### Scoping
- **A client project - unlock order misread**: a doc presented training runs sequentially for clarity; the client meant grouped (any-order within a group). Presentation was mistaken for enforcement. *Proposed rule: if a doc presents things in order, ask whether the order is enforced or just presentational.* Tags: [#scoping]
- **A client project - deployment approach churned 3×**: never asked during scoping; changed from 1 → 2 → level-by-level → 3 batches. *Proposed rule: ask deployment approach during scoping, before milestones.* Tags: [#scoping]
- **A client project - pre-launch state unscoped**: a "coming soon" screen was missed until the user journey was traced for accounts created before the feature was live. *Proposed rule: trace every user state, including states where features aren't ready.* Tags: [#scoping]
- **A client project - content in two contexts**: some screens appeared both inline and in a full index; no architecture for it. *Proposed rule: ask about content that appears in multiple contexts.* Tags: [#scoping]
- **A client project - interaction mechanic unspec'd, cost two deploy cycles**: a quiz mechanic (commit timing, verdict visibility, Back behavior) was assumed, built, shipped - then re-shipped twice as the client clarified. Each clarification was free feedback because nothing was locked. *Proposed rule: during design analysis, lock every button-press / state-transition / click-to-something in writing, signed off next to its screen, before code. Make "Mechanic spec lock" its own milestone. Anything not signed off and later "decided" is a change request, not feedback.* Tags: [#spec-lock]

### API / schema
- **A client project - mirrored system not fully mirrored**: system A had full unlock logic, mirror system B returned everything available. *Proposed rule: if A mirrors B, check every feature of A against B.* Tags: [#api]
- **A client project - missing submit endpoint**: had GET /start, no POST /submit; caught late in QA. *Proposed rule: if there's a /start, there must be a /submit or /complete.* Tags: [#api]
- **A client project - enum casing drift**: same status value spelled two ways across the codebase. *Proposed rule: enum values defined once in the API contract, referenced everywhere.* Tags: [#api]
- **A client project - JSON column undocumented**: schema had the column, contract didn't specify per-event structure. *Proposed rule: JSON columns need structure documented per use case.* Tags: [#api]
- **A client project - architecture change buried in a message**: a crop/rendering change reached the dev only via a credentials message. *Proposed rule: architecture changes affecting the dev go in the dev brief, not just a message.* Tags: [#api]

### Documents
- **A client project - QA checker scoped too narrow**: only scanned one folder; info-wall violations hid in headers, last-updated lines, QC logs of other folders for weeks. *Proposed rule: QA checker scans ALL folders producing team-facing docs from day one.* Tags: [#docs]
- **A client project - PDF design drifted across regenerations**: no saved generation script, so each regen looked different. *Proposed rule: save PDF/generation scripts from the first generation; reuse, never regenerate from scratch.* Tags: [#docs]
- **A client project - GREEN reported against stale container copies**: actual persisted files still had violations. *Proposed rule: verify document changes by reading the real persisted files, not container copies.* Tags: [#docs] [#process]
- **A client project - retired term lingered**: old terminology remained after an architecture change. *Proposed rule: when a term is retired, grep for it across ALL docs.* Tags: [#docs]
- **A client project - completion PDF claimed unverified results**: stated data was "imported and verified" when nobody had imported anything; the number came from the spec, not from staging. *Proposed rule: completion reports describe what DID happen; never claim verification in a client-facing doc without personally checking or the owner confirming.* Tags: [#docs] [#clientcomms]

### Team management
- **A client project - task-by-task reviews burned hourly TL**: multiple review rounds on a fixed-price dev. *Proposed rule: full-milestone reviews, two rounds max.* Tags: [#team]
- **A client project - first TL dropped on first task**: over-quoted a simple transfer task and pushed comms off-platform. *Proposed rule: two red flags on the first task = drop immediately.* Tags: [#team]
- **A client project - second TL padding patterns; but found real bugs**: padded retests and billed unrelated browsing; yet found 2 real browser-only bugs. Resolution: adopt the three-layer review (the coding agent code review free + QA browser + conditional TL). *Proposed rule: code review catches code bugs (free, the coding agent); QA catches browser bugs; reserve TL for architecture/security/deployment.* Tags: [#team] [#promoted-to-rules]
- **A client project - ClickUp setup mis-priced as PM work**: it's data entry. *Proposed rule: the coding agent writes the ClickUp doc; a VA copies it at fixed price ($30-50).* Tags: [#team] [#clickup]

### Client comms
- **A client project - re-asked an already-answered question**: drafted a clarification already documented across prior sessions. *Proposed rule: cross-reference existing docs before drafting client questions.* Tags: [#clientcomms]
- **A client project - "we" leaked into a client message**: white-label violation. *Proposed rule: run the white-label checklist on EVERY client-facing output.* Tags: [#clientcomms]

### Process / infrastructure
- **A client project - info-wall leak in a contractor-facing ClickUp comment**: "decision pending from client" attributes a source to a team member. *Proposed rule: white-label + info-wall scan applies to every ClickUp comment/task to a contractor, not just client-facing messages.* Tags: [#process] [#clientcomms]
- **A client project - checklist vs comment**: action items buried in a long comment get read once; a checklist item stays at the top until checked. *Proposed rule: trackable action items go in the checklist field, not comments.* Tags: [#clickup]
- **A client project - gate placed on the wrong milestone**: the gate depended on a flag only set in a later milestone, so it couldn't be tested in scope. *Proposed rule: every gate must be triggerable by the flow its own milestone delivers; cross-check against the data model.* Tags: [#process] [#clickup]
- **A client project - concluded a tool was unavailable after two searches**: it had been used in a prior session. *Proposed rule: if a capability was used before, try 3+ search-term variations before concluding absence; then acknowledge and work around.* Tags: [#process]
- **A client project - silent dev push diverged ClickUp from GitHub**: dev pushed fixes without commenting; ClickUp showed failed, GitHub showed fixed. *Proposed rule (now in rules.md as clickup-github-divergence): check BOTH ClickUp and GitHub; on divergence GitHub is truth; require devs to comment the commit hash on push.* Tags: [#process] [#promoted-to-rules]
- **A client project - large binaries committed to the repo**: ~80-100MB of audio + a plugin zip pushed to git despite the dev's own "move to CDN" TODO. *Proposed rule: tell devs explicitly - no binary assets in git (audio/image/video/zips → S3/CDN), `.gitignore` from day one.* Tags: [#process]
- **A client project - code review passed but manual QA found UX gaps**: missing exit button / header surfaced only in a manual staging test. *Proposed rule: never close a milestone on code review alone; Layer 2 browser QA is mandatory.* Tags: [#process] [#team]

### ClickUp structure
- **A client project - over-granular ClickUp (93 flat endpoint-level tasks)**: a VA charged but only finished a fraction. *Proposed rule: ClickUp docs simple enough for one fixed-price VA job; deliverable-level tasks, endpoints as subtasks/checklist items; milestone = section not task; simple top-to-bottom lists not tables; write real task numbers in dependencies; "High" priority only for critical-path/blocking.* Tags: [#clickup]

---

## Promotion log

| Date | Observation → Rule | Location |
|------|-------------------|----------|
| 2026-06-04 | Three-layer review adopted org-wide for client delivery | rules.md (Decision rules) |
| 2026-06-04 | clickup-github-divergence: GitHub is truth | rules.md + both hierarchy files |

### 2026-06-13 - Docling document-parsing layer added (v0.3.0)
- Wired **Docling** (MIT, 61,489★, MCP, verified live 2026-06-13) as the INPUT/parsing layer feeding the existing doc-generation bundle: inbound contracts/RFPs/SOWs/scans/spreadsheets -> Docling -> structured Markdown/JSON + tables -> fills project.js + Doc 1-8 instead of manual transcription. *Rule promoted:* parse inbound docs first (extends READ-BEFORE-ASKING), parse sensitive docs locally, verify extracted figures against source before they enter a client doc. (See rules.md + references/docling-parsing-layer.md.)
- Gate 0 honored: doc-generation bundle, registry, interview protocol, STATUS.md routing all UNCHANGED - Docling changed the input only. Tags: [#docling] [#intake] [#doc-generation]

### 2026-06-15 - DEEPEN: spec-driven handoff discipline (v0.6.0)
- Absorbed **github/spec-kit** (MIT, 112,273 stars; methodology only - CLI/templates/agent files NOT installed) as the ARTIFACT SHAPE for a locked spec: constitution -> versioned PR-reviewable spec -> clarify gate -> plan -> tasks (= ClickUp doc) -> analyze coverage -> self-checklist. Gate-0 PASS: spec-LOCK was a sign-off discipline only; it had no artifact-shape/coverage-gate and no PR-reviewable-spec-as-client-deliverable. *Rule promoted:* shape the locked spec on the ladder, run clarify + requirement-to-task coverage BEFORE build, optionally ship the spec/plan/tasks as a white-label client deliverable (signed-off spec = billable baseline). spec-lock primacy + three-layer review + billing-model rule + doc bundle/registry UNCHANGED. Boundary: product-manager authors product specs; cloud-architect owns the plan. (See rules.md + spec-driven-handoff-2026.md.) Tags: [#spec-lock] [#docs] [#process]
## Sources

- Upstream: alirezarezvani/the coding agent-skills (MIT); PROJECT_TAKEOVER + codebase-onboarding + migration-architect + docling-parsing-l (n/a)
- What was used: noted: alirezarezvani/the coding agent-skills; methodology absorbed: PROJECT_TAKEOVER + codebase-onboarding + migration-architect + docling-parsing-l; rejected (not used): sdi2200262/agentic-project-management, opf/openproject, client-portal / client-management GitHub topics
- License notes: opf/openproject: GPL-3.0 (FLAG)
