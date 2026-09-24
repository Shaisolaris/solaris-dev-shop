# Codebase Takeover and Audit (Inherited Client Code)

Methodology pack for the moment Solaris inherits a client codebase: a handoff, a rescue, due diligence on a repo before quoting, or a takeover from a prior dev shop. The existing review machinery (rules.md 7-phase Full Audit, trivy/semgrep/osv/gitleaks scanning, claude-context indexing) answers "is this change safe?" This file answers the prior question: "what IS this thing, who really wrote it, where are the buried bodies, and can we trust our own read of it?"

Six methods, lifted methodology-only from ECC (affaan-m/ECC, MIT). Run them in the order below on first contact with unfamiliar inherited code. None of them replaces a tool already in the stack; they are reasoning protocols the scanners cannot do.

Source map (methodology absorbed, no code/prompts vendored):
- code-explorer (agent) -> execution-path tracing of unfamiliar code
- repo-scan (skill) -> file classification + embedded third-party detection + 4-level verdict
- silent-failure-hunter (agent) -> swallowed-error bug class
- inherit-legacy-style (skill) -> match the inherited codebase's own conventions
- click-path-audit (skill) -> UI-flow state-interaction audit
- santa-method (skill) -> two-agent adversarial verification of the audit itself

---

## 1. Surface census FIRST: classify every file (from repo-scan)

Before reading logic, answer ownership. On an inherited repo you do not yet know how much code is actually the client's, how much is vendored third-party copied into the tree (not declared in any package manager), and how much is dead weight. Scanners that read package manifests miss in-tree vendored libraries entirely, and those are exactly where stale CVEs and license landmines hide.

Pass over the whole repo and tag every file into one of three buckets:
- **Project code** - written by/for the client, the actual asset.
- **Embedded third-party** - a library copied into the source tree (vendored FFmpeg, a forked SDK, a snapshotted jQuery, a copy-pasted utils file from another project). Detect via directory names, file headers, bundled LICENSE files, and version markers, NOT via package.json. Record the detected library and its likely version.
- **Build artifact / dead weight** - committed build output, obj/, ipch/, generated bundles, vendored binaries, debug dumps. Often the bulk of repo size and pure noise.

Then group files into modules/subsystems and give each module exactly one of four verdicts:

| Verdict | Meaning | Takeover action |
|---|---|---|
| Core Asset | Client-owned, load-bearing, worth maintaining | Onboard properly, document, test |
| Extract & Merge | Duplicated or near-duplicated logic (same wrapper copied 3x) | Consolidate to one source of truth |
| Rebuild | Owned but so degraded that fixing costs more than replacing | Quote a rebuild, not a patch |
| Deprecate | Dead code, abandoned feature, committed artifacts | Delete; reduces attack surface and audit cost |

Depth tiers (right-size to repo scale): fast reads 1-2 files/module for a quick inventory of a huge tree; standard reads 2-5/module (default); deep reads 5-10/module and adds thread-safety / memory / API-consistency checks; full reads everything pre-merge. Start standard; drop to fast for 100+-module monorepos; run deep only on modules already flagged Rebuild.

Why this is first: the census tells the rest of the audit where to spend effort. Vendored-third-party buckets feed straight into the supply-chain / license / CVE pass (a 2015-vintage in-tree FFmpeg is a finding the manifest scanners never see). Deprecate-bucket files should be removed before they waste review hours. The four-level verdict is also the honest input to the takeover quote: a repo that is 60% Rebuild is a different bid than one that is 90% Core Asset.

License/supply-chain hook: every embedded-third-party hit is also a license question. A copyleft (GPL/AGPL) library vendored into a closed client product is a P0 legal finding; route to the license-flag doctrine in rules.md and to the security-auditor. The in-tree copies are higher-risk than declared deps because nobody is tracking their CVEs.

---

## 2. Trace execution paths before judging anything (from code-explorer)

You cannot review code you do not understand, and unfamiliar inherited code is the case where the temptation to skim is strongest. Before forming any verdict on a feature, trace it end to end:

1. **Entry-point discovery** - find where the feature actually starts: the route, the event handler, the cron, the queue consumer, the user action. Not where you assume it starts.
2. **Execution-path tracing** - follow the call chain from entry to completion. Note every branch, every async boundary, every data transformation, and crucially every error path.
3. **Architecture-layer mapping** - which layers does this touch (controller / service / data / external)? How do they talk? Where are the clean boundaries and where are the leaks?
4. **Pattern recognition** - what abstractions and naming conventions already exist? (This is the input to method 4 below.)
5. **Dependency documentation** - external libs/services this path depends on, internal modules it couples to, shared utilities worth reusing rather than re-implementing.

Output per traced feature: Entry Points, Execution Flow (numbered steps), Architecture Insights, a Key Files table (file / role / importance), Dependencies (external + internal), and Recommendations (what to follow, what to reuse, what to avoid). On a large repo this is where claude-context indexing earns its keep: index first, then trace by intent instead of grepping exact strings.

This step is what makes the takeover quote defensible. "We traced the checkout flow; it touches 9 modules across 3 layers and depends on a deprecated payment SDK" is an estimate. "It looks complicated" is not.

---

## 3. Hunt silent failures: the swallowed-error bug class (from silent-failure-hunter)

Inherited code accumulates silent failures because they never crash in front of the prior team. They are the single highest-yield bug class in a takeover and the one normal review passes skim past, because nothing throws. Hunt them with zero tolerance:

- **Empty/ignored catches** - catch {}, catch (e) {} with no action, errors converted to null or [] with no log and no context.
- **Inadequate logging** - logs missing the context needed to diagnose, wrong severity (an error logged at debug), log-and-continue where the operation actually failed.
- **Dangerous fallbacks** - default values that mask a real failure; .catch(() => []) that turns "the API is down" into "the user has no items"; graceful-looking paths that just move the bug downstream where it is harder to find.
- **Broken propagation** - lost stack traces, generic rethrows that erase the original cause, un-awaited promises, missing async error handling.
- **Missing handling entirely** - no timeout/error handling around network/file/DB calls; no rollback around transactional work.

Report each as: location, severity, issue, impact, fix. Feed confirmed findings into the rules.md severity taxonomy ("error silently swallowed" is already a red flag there; this method is the systematic sweep behind it). On a rescue project, expect this pass to surface the actual cause of the "intermittent" bugs the client could never reproduce.

---

## 4. Match the codebase's conventions, do not impose yours (from inherit-legacy-style)

The fastest way to make an inherited codebase worse is to "fix" its style. When Solaris (or an AI agent on the project) starts writing into legacy code, the default failure is style drift: imposing mainstream/pretrained idioms onto a hand-written project that had its own internally-consistent conventions. The result is a codebase that is half one style and half another, which is worse than either alone.

Before writing into inherited code, scan it across four meta-architecture dimensions (this is alignment of structure, NOT a judgment of syntax or tech-stack quality):
1. **File anatomy** - in-file declaration order (imports -> types -> main logic -> helpers -> exports).
2. **State & control flow** - naming conventions for async state, pagination, flags, loading.
3. **Infrastructure** - where cross-cutting utilities live (interceptors, formatters, middleware).
4. **Error handling** - try/catch vs global interceptor vs Result-return; null-check habits.

Apply a signal threshold so you do not over-correct on noise: a lopsided split (an 800-vs-8 naming convention) auto-resolves to the majority; only a near-even split or a genuine fork on a core dimension is worth raising. When you must raise a conflict, raise exactly ONE at a time with the evidence (path A does X, path B does Y) and let the decision be made deliberately; never stack questions.

Crystallize the result into a project-root style rules file with three sections: Golden Files (real exemplar paths annotated with what they demonstrate), concrete checkable Naming/State rules, and DONTs (anti-patterns that must not propagate). Reuse exemplar STRUCTURE but never copy an exemplar's bugs - flag defects, do not propagate them. This file becomes the standing constraint on all subsequent work on that client, and is exactly what onboards a freelancer onto the project without restyling it.

---

## 5. Click-path audit: UI bugs static reading misses (from click-path-audit)

Some inherited bugs survive every code-reading pass because each function is individually correct: the wiring exists, nothing crashes, the types are right. The bug is in the interaction of state changes. The canonical case: a "New Email" button called setComposeMode(true) then selectThread(null) - and selectThread had a side effect resetting composeMode to false. Both calls worked; the button did nothing. Pure code reading cannot see this.

Run this when the client reports "this button does nothing" / "broken UI" but systematic debugging found no defect, or after any refactor touching a shared state store (Zustand/Redux/context).

**Step 1 - build the side-effect map FIRST.** For every store action/setter, document not just what it sets but what it RESETS as a side effect. Flag "dangerous resets": actions that clear state they do not own. This map is the entire game; the example bug is invisible without knowing selectThread resets composeMode.

**Step 2 - audit each touchpoint.** For every button/toggle/submit, trace every call in the handler in order; for each call record what it reads, writes, and resets; then check: does a later call UNDO an earlier call's state change? Is the FINAL state what the button label promises? Are there async races? Six recurring patterns to check by name: Sequential Undo, Async Race, Stale Closure, Missing State Transition, Conditional Dead Path, useEffect Interference.

**Step 3 - report** each finding with touchpoint, pattern, ordered trace showing the conflict, expected vs actual, and a specific fix. For a full-app sweep, map all stores first (shared context) before auditing pages in parallel. Every bug found here should get a regression test.

---

## 6. Verify the audit adversarially before delivering it (from santa-method)

A takeover audit is a deliverable the client makes decisions and pays against. A single agent reviewing its own audit shares the exact biases, knowledge gaps, and blind spots that produced it. Before delivering a takeover report, verify it with two INDEPENDENT reviewers.

Loop: GENERATE the audit -> two reviewers check it in parallel against the SAME objective rubric, with NO shared context and no sight of each other's verdict -> verdict gate: both PASS = ship, otherwise collect all flags, fix only those, re-run with FRESH reviewers (no memory, to avoid anchoring) -> cap at ~3 iterations, then escalate to a human.

Why both must pass: if only one reviewer catches an issue, the issue is real and the other reviewer's miss is precisely the blind spot this method exists to eliminate. Keep the rubric objective (pass/fail conditions, not style opinions) so reviewers flag errors, not preferences - for a takeover audit the rubric covers: completeness (every module got a verdict), factual accuracy (claimed dependencies/versions actually exist in the tree), no fabricated findings, internal consistency, and severity correctness.

This is the semantic-verification layer; run it AFTER the deterministic passes (build/lint/test, trivy/semgrep/osv/gitleaks) have already cleared. Cost is roughly 2-3x a single pass, which is cheap against shipping a wrong takeover quote or missing the finding that sinks the project. For very large audits, sample-verify rather than full-verify every module.

---

## Takeover run order (one-line)

census (1) -> trace the load-bearing features (2) -> silent-failure sweep (3) -> capture conventions before writing (4) -> click-path audit if UI-heavy (5) -> adversarial verify the report (6) -> fold confirmed findings into the rules.md severity taxonomy + the takeover quote.

## Cross-references
- rules.md - severity taxonomy, red flags, 7-phase Full Audit, small-task lanes. Decision rule "inherited codebase -> Full Audit" is the trigger for this whole file.
- references/trivy-sca-secrets-sbom.md + static-analysis-and-pr-automation.md - the deterministic scanning layer these reasoning methods sit on top of. The embedded-third-party bucket from method 1 feeds the supply-chain/license/CVE pass directly.
- claude-context-operator.md - index any >2,000-file inherited repo BEFORE method 2 tracing.
- security-auditor - hand every embedded-third-party + license finding from method 1, and every confirmed swallowed-error with a security angle from method 3, across the line.

## Memory scope keys
Log takeover findings under stable keys so they survive across sessions on the same client:
- code-reviewer/takeover/<client>/census - file classification + 4-level module verdicts
- code-reviewer/takeover/<client>/embedded-libs - vendored third-party + versions + license flags
- code-reviewer/takeover/<client>/silent-failures - confirmed swallowed-error sites
- code-reviewer/takeover/<client>/conventions - the captured style rules (Golden Files / DONTs)
