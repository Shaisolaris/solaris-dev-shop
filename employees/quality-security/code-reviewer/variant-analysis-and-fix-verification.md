# Variant analysis and fix-verification (review techniques)

Two review techniques that operate on a CONFIRMED issue, distinct from the two files they sit beside. references/static-analysis-and-pr-automation.md is the scanning STACK (run Semgrep/OSV/gitleaks/danger to produce evidence). references/codebase-takeover-and-audit.md is FIRST-CONTACT reasoning on inherited code (census, trace, silent-failure, conventions, click-path, adversarial verify of the audit). This file is the REVIEWER's move once a bug is in hand: do not just fix the one line - find every sibling of it, and when a PR claims to fix something, prove the fix actually holds and closes the whole class.

Lifted methodology-only from trailofbits/skills (Trail of Bits Claude Code skills marketplace, 5.5k stars, CC-BY-SA-4.0 - SEE LICENSE FLAG BELOW). Specifically the variant-analysis, fp-check, and differential-review plugins, plus the semgrep-rule-creator rule-as-search idea. NO skill code, prompts, SKILL.md text, Python, or rule packs were copied, vendored, run, or bundled - this is original prose describing the workflow patterns.

## LICENSE FLAG (read before reuse)
trailofbits/skills is CC-BY-SA-4.0 (Creative Commons Attribution-ShareAlike 4.0) - NOT a permissive software license, it is a copyleft CONTENT license. The user gate required permissive-or-flag; this is flagged. Mitigations: (a) methodology-only, our own prose, no copied text/code; (b) attribution given here and in plugin.json absorbed_from (satisfies CC-BY); (c) not redistributing their work or a text derivative, so ShareAlike is not triggered by this internal note. Do NOT vendor or fork any file from that repo; route any future reuse of their actual content to legal.

---

## Why these two techniques

The default review failure is one-bug-one-fix tunnel vision. A reviewer spots a missing auth check on one endpoint, requests a fix on that endpoint, approves the PR - and the same missing check on four sibling endpoints ships untouched. And the default re-review failure is approving a "fix" PR on the strength of the description without confirming the fix is real, complete, and free of new bugs. Both failures are about CLASS and PROOF: a confirmed bug is evidence of a pattern (find the siblings), and a claimed fix is a hypothesis (verify it).

These complement, not duplicate, the existing files: static-analysis-and-pr-automation.md tells you HOW to run the scanners that surface the first bug; this file tells you what to do with a bug once it is confirmed. codebase-takeover-and-audit.md hunts bugs on first contact with unfamiliar code; this file is the per-bug and per-fix discipline applied to any review, especially diffs and PRs.

---

## Technique 1 - Variant analysis in review (one finding -> all its siblings)

When you confirm any non-trivial finding in a review, do not close it as a single comment. Treat it as a seed and sweep for the class.

### The reviewer's variant loop
1. **State the root-cause pattern in one sentence.** Not "missing auth on `/orders`" but "endpoints that read a resource by id without checking the caller owns it." The sentence is the search.
2. **Inventory the sink class in the diff AND the surrounding code.** Every place the same operation happens: every endpoint of that shape, every query builder, every deserialize, every redirect, every file path join, every place that trusts the same header/claim. The PR diff is the trigger; the whole module (or repo) is the search space, because a fix that closes the diff but leaves the siblings is a false sense of safety.
3. **Search by structure, not by string.** grep finds the exact symbol; it misses the same bug under a different name. Use the AST/taint engine from static-analysis-and-pr-automation.md (Semgrep) with a pattern matching the SHAPE of the bug - the pattern IS the variant search. On a >2,000-file repo, index with claude-context first (see claude-context-operator.md) and search by intent, then confirm structurally.
4. **Apply the three reachability questions to each candidate** (same discipline as the security-auditor bounty trace): user-controlled input, reaches the sink unsanitized, reachable from a real boundary. A candidate that passes is a variant; one broken by a real guard/sanitizer is not.
5. **Report the class, not the instance.** The review comment becomes: "this pattern (root cause) appears at these N sites (list); fix all N, not just the one in this diff." This is the difference between a reviewer who patches a symptom and one who closes a vulnerability class.

### Where this lands in the existing modes
- Security Audit mode: after enumerating input surfaces, every confirmed finding triggers a variant sweep before the finding is written up.
- PR Review touching auth / query construction / deserialization / templating / shell-out / file paths: any issue found is checked for siblings in the same files the PR touches AND the modules those files belong to.
- Dependency / takeover: pairs with the embedded-third-party census - a bad pattern in vendored code often has the same author's siblings nearby.

NET-NEW vs the existing files: static-analysis-and-pr-automation.md runs scanners to find first-pass candidates; variant analysis is the seed-driven, root-cause-shaped sweep that generic scans miss because no off-the-shelf rule encodes this specific codebase's specific mistake. codebase-takeover-and-audit.md is first-contact discovery, not per-finding class closure.

---

## Technique 2 - Fix-verification review (prove the fix actually fixes it)

When a PR claims to fix a bug (a reported issue, a prior review finding, a security advisory, a "fixes #123"), the reviewer's job is not to confirm the code changed - it is to confirm the bug is gone, the whole class is closed, and nothing new broke. Approving a fix on its description is how incomplete fixes ship.

### The fix-verification checklist (run on every fix PR)
1. **Root cause, not symptom.** Read the original bug, abstract its root cause (Technique 1 step 1), and confirm the patch addresses THAT. A patch that edits the one reported line but leaves the root cause (e.g. a missing central guard) is incomplete - request the real fix.
2. **Reproduce-then-confirm.** If a reproduction or PoC exists, confirm it now fails against the patched code. If none exists, ask for one (or a failing-then-passing test) - a fix with no demonstration that the bug was real and is now gone is unverified.
3. **Probe the obvious bypasses.** Blacklist fix -> try encoding/case/Unicode/double-encoding. Client-side fix -> try the direct API call. Regex fix -> try a payload outside the regex. Length/type check -> try the boundary. Spend real adversarial thought; an attacker will.
4. **Variant check the fix.** Run Technique 1 on the fixed bug: does the patch close every sibling, or only the one in the diff? Re-run the structural pattern tree-wide. Any remaining hit means the fix is partial - the PR closes the ticket but not the class.
5. **Hunt fix-introduced bugs.** A patch can add its own defect: a new "sanitizer" that is itself bypassable; a try/catch wrapped around the fix that now silently swallows the real error (cross-ref the silent-failure class in codebase-takeover-and-audit.md); an over-broad change that breaks a valid path; a perf regression. Diff-review the patch with full rigor, not a rubber stamp because it is "just a fix."
6. **Regression guard required.** A fix without a test will come back. Require a regression test that exercises the exploit/bug path (red before, green after), and where the pattern is detectable, a custom static rule (Semgrep) wired into CI so the whole class cannot silently return. The rule is authored test-first: it must fire on the original bad code and stay silent on the corrected code.
7. **Confirm the commit touches the root-cause code.** Use git history (differential review): a fix commit that only edits tests, comments, or config to make CI green - without touching the code that contained the bug - is a red flag and an auto-request-changes.

### Verdict
Approve a fix PR only when ALL hold: root cause addressed, repro/PoC now fails, obvious bypasses fail, variant sweep is clean, no fix-introduced bug, regression guard present, commit touches root-cause code. Short of all seven -> request changes with the specific gap, never an LGTM.

### Differential / diff-scoped discipline
Scope the DEEP read to the diff and its blast radius (the callers and state the changed code touches), but always run the relevant structural rules tree-wide so a change in one file cannot mask an untouched variant elsewhere. This is the same diff-aware posture as `--baseline-commit` scans in static-analysis-and-pr-automation.md, now applied to the reviewer's judgment, not just the scanner.

---

## Cross-references
- references/static-analysis-and-pr-automation.md - the scanning stack (Semgrep/OSV/gitleaks/danger) that produces candidates and runs the structural rules these techniques rely on; the AST taint engine is the variant-search tool. NO tool list duplicated here.
- references/codebase-takeover-and-audit.md - first-contact reasoning; the silent-failure class is referenced in fix-verification step 5 (fix-introduced swallowed errors), and any finding from a takeover triggers Technique 1.
- claude-context-operator.md - index >2,000-file repos before a variant sweep so the structural search runs by intent across the whole tree.
- rules.md - severity taxonomy + red flags + the no-description/no-tests/>400-LoC decision rules; the fix-verification verdict and the variants list feed the review write-up there.
- security-auditor references/audit-firm-methodology.md - the AUDIT-side mirror of this file (variant analysis + custom-rule authoring + fix-verification run at full-engagement scale rather than PR scale). Same methodology, different scope; hand cross-class security findings across the line.

## Memory scope keys
- code-reviewer/<project>/variants/<finding-id> - the sibling class found by a variant sweep (file/line/root-cause-pattern each), so a later PR touching a sibling is caught
- code-reviewer/<project>/fix-verification/<pr-or-finding-id> - per-fix verdict (approved/request-changes) + repro re-run result + bypass attempts + tree-wide variant result
- code-reviewer/<project>/custom-rules - structural rules authored from this project's confirmed findings (provenance + bad/good examples); WE-authored, kept separate from any registry rule per the license posture in static-analysis-and-pr-automation.md
