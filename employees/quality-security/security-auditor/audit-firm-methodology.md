# Audit-firm methodology: variant analysis, custom-rule authoring, fix-verification

The PROFESSIONAL-AUDIT-WORKFLOW layer, distinct from the three files it sits beside. references/scanning-stack.md is the tool/check CATALOG (the WHAT: Semgrep/OSV/gitleaks/pytm/Nuclei + fleet checks FA-1/FA-2). references/trivy-and-dast.md is the operational SCAN workflow (the HOW-to-run a single scanner). references/adversarial-bounty-hunting.md is the attacker MINDSET (the HOW-to-think / does-it-actually-pay triage on a single finding). This file is the FIRM-GRADE LOOP that runs after a finding is confirmed: how a real audit shop turns one confirmed bug into full-class coverage, codifies it as a reusable detector, and proves the fix actually holds.

Lifted methodology-only from trailofbits/skills (Trail of Bits a coding agent skills marketplace, 5.5k stars, CC-BY-SA-4.0 - SEE LICENSE FLAG BELOW). Specifically the variant-analysis, semgrep-rule-creator, semgrep-rule-variant-creator, fp-check, and differential-review plugins. NO skill code, prompts, SKILL.md text, Python, or rule packs were copied, vendored, run, or bundled - this is an original-prose description of the workflow patterns those plugins embody.

## LICENSE FLAG (read before reuse)
trailofbits/skills is licensed CC-BY-SA-4.0 (Creative Commons Attribution-ShareAlike 4.0), which is NOT a permissive software license - it is a copyleft CONTENT license. The user gate required permissive-or-flag; this is flagged. Mitigations applied: (a) methodology-only - we read the patterns and wrote our own description, we did not copy their text or code; (b) attribution is given here and in plugin.json absorbed_from (satisfies CC-BY); (c) we are not redistributing their work or a derivative of their text, so the ShareAlike obligation is not triggered by this internal methodology note. Do NOT vendor, fork into a client deliverable, or copy-paste any file from that repo - if a future pass wants their actual rules or scripts, treat the whole repo as copyleft content and route to legal first.

---

## Why a separate loop

A scan-and-triage audit (scanning-stack -> bounty-mindset) ends when one finding is confirmed exploitable. A real audit firm does not stop there. One confirmed SQL injection in `getUser()` is evidence that the same anti-pattern probably exists in the other 40 query builders the same team wrote. Stopping at the single finding leaves the client patched in one spot and breached in another. The firm-grade loop closes the whole bug CLASS, not the single instance:

confirmed finding -> variant analysis (find every sibling) -> codify as a custom rule (so it never regresses, and so the sweep is reproducible) -> fix-verification (prove each fix actually closes the bug and introduced no variant) -> regression rule wired into CI.

Run this AFTER a finding has passed the bounty quality gate in adversarial-bounty-hunting.md. The mindset file tells you a finding is real; this file tells you what a firm does with a real finding.

---

## Part 1 - Variant analysis (one bug -> the whole class)

The single highest-leverage move in professional auditing. The premise: bugs cluster. A developer who made one mistake (forgot to parameterize a query, trusted one user-controlled path, missed one auth check) almost certainly made it again wherever the same mental model applied. The confirmed finding is the SEED; variant analysis harvests the field.

### The variant-analysis loop
1. **Abstract the root cause, not the symptom.** "SQLi in `getUser`" is the symptom. The root cause is the PATTERN: "user input concatenated into a SQL string instead of a bound parameter." Variant analysis searches for the pattern, not the line. Write the pattern down in one sentence before searching - this is what you will turn into a rule in Part 2.
2. **Enumerate the sink class.** List every place the dangerous operation occurs: every raw query call, every `exec`/`system`, every deserializer, every template render, every redirect, every file-path join. The sink inventory is the search space.
3. **For each sink, ask the three taint questions** (same as the bounty trace, run breadth-first now instead of depth-first on one path): is the input user-controlled, does it reach this sink unsanitized, is the path reachable from a real boundary. A sink that passes all three is a variant.
4. **Search by structure, not by string.** grep finds `getUser`; it does not find the same bug spelled differently in `fetchAccount`. Use the AST/taint engine (Semgrep, see scanning-stack.md) with a pattern that matches the SHAPE of the bug. This is why variant analysis and rule-authoring (Part 2) are the same activity from two angles: the rule IS the structural search.
5. **Cross-language / cross-service variants.** If the codebase is polyglot or microservice, the same logic flaw often reappears in another language's implementation of the same feature (the Node gateway and the Go worker both trust the same header). Port the pattern across languages (see semgrep-rule-variant-creator pattern in Part 2).
6. **Record every variant** with the same evidence discipline as the seed finding (file, line, taint path, reachability) so each is independently confirmable and the client can patch the whole class in one sprint.

### Variant analysis vs the existing files
- Bounty-hunting (adversarial-bounty-hunting.md) goes DEEP on one path to prove it pays. Variant analysis goes WIDE across all siblings of an already-proven bug. Different axis, complementary order: prove one, then find the rest.
- This is NET-NEW: scanning-stack.md runs scanners to find candidates from scratch; variant analysis is the targeted, seed-driven sweep that a generic scan misses because no generic rule encodes this specific team's specific mistake.

---

## Part 2 - Custom-rule authoring (codify the finding so it cannot hide or regress)

A confirmed finding plus its variants should not live only in a PDF. Encode the root-cause pattern as a custom static-analysis rule (Semgrep YAML is the working format named in scanning-stack.md). The rule does three jobs at once: it performs the structural variant search of Part 1, it becomes the regression guard of Part 4, and it is a reusable asset for the next client with the same stack.

### Test-driven rule authoring (the firm discipline)
Authoring a rule without test cases produces a rule that either misses real bugs (false negatives) or screams at safe code (false positives) - either way the client stops trusting it. Author every rule test-first:
1. **Collect true-positive cases** - the confirmed finding plus its variants from Part 1. The rule MUST fire on every one.
2. **Collect true-negative cases** - the safe versions: the same operation done correctly (parameterized query, sanitized input, guarded path). The rule MUST NOT fire on these. Pull these from the same codebase so the rule is tuned to this team's real safe idioms.
3. **Write the smallest pattern that separates the two sets.** Start specific (matches the exact sink + taint shape), then generalize only as far as the negatives still pass. Over-generalizing is the number-one cause of a noisy rule.
4. **Run against the whole repo.** New hits are either new variants (good - add to findings) or false positives (bad - tighten the pattern or add a `pattern-not` exclusion for the safe idiom).
5. **Tune metavariables and dataflow.** Use taint mode (`pattern-sources` / `pattern-sinks` / `pattern-sanitizers`) so the rule tracks reachability, not just textual shape - a sanitizer in the path must suppress the finding, matching the bounty-mindset rule that a broken taint chain is not a finding.
6. **Document the rule** with: the CWE, the one-sentence root cause from Part 1, an example bad and good, and the confirmed finding it was born from. A rule without provenance gets deleted by the next maintainer who does not know why it exists.

### Porting a rule to new languages (variant-creator pattern)
When the same flaw class spans languages, do not hand-write each from scratch. Take the validated rule for language A, identify the equivalent sink/source/sanitizer constructs in language B, port the pattern, then RE-RUN the test-first cycle with language-B true-positive and true-negative cases. A ported rule is not trusted until it has passed its own tests in the new language - the porting does not carry over the validation.

### License posture for rules
Semgrep ENGINE is LGPL-2.1 (run the CLI, do not vendor the binary). Semgrep REGISTRY rule packs are under a separate source-available license - do NOT fork registry rules into a closed client deliverable. Rules WE author from a client's own confirmed findings are our work product (subject to the engagement's IP terms); keep them separate from any registry-derived rule. The trailofbits methodology that inspired this section is CC-BY-SA-4.0 content - see the LICENSE FLAG at the top; this file is original prose, not a copy.

---

## Part 3 - Fix-verification (prove the patch actually closed the bug)

The most-skipped and highest-value step. A patch that "looks like it fixes it" is not verified. Firms re-audit every fix because incomplete and incorrect fixes are common: the patch addresses the symptom not the root cause, fixes one variant and misses three, adds a new bug, or is defeated by a trivial bypass. A re-breach on a finding the client paid to have fixed is the worst outcome a firm can ship.

### The fix-verification checklist (run per fixed finding)
1. **Root cause, not symptom.** Confirm the fix addresses the abstracted root cause from Part 1, not just the one reported line. An input-validation patch on the single reported endpoint is suspect if the root cause was a missing central guard.
2. **Re-run the original PoC.** The minimal exploit from the bounty workflow must now fail. If there is no PoC, the original finding was not firm-grade - build one before claiming a fix is verified.
3. **Attempt the obvious bypasses.** A blacklist fix invites encoding/case/Unicode bypass; a client-side fix invites a direct API call; a regex fix invites a payload the regex misses. Spend the same adversarial effort on the fix that you spent on the finding.
4. **Re-run the custom rule from Part 2 across the whole tree.** This is why the rule was authored: it proves not just the seed but every variant is closed. Any remaining hit is an incomplete fix - report it as a re-open, not a new finding.
5. **Check for fix-introduced variants.** A patch can add its own bug (a new query string built to "sanitize" that is itself injectable; a try/catch added around the fix that now silently swallows the real error - cross-ref the code-reviewer silent-failure class). Diff-review the patch with the same rigor as the original code.
6. **Confirm a regression test exists.** A fix without a test will regress. The regression guard is the custom rule (wired into CI, Part 4) plus, ideally, a unit/integration test that exercises the exploit path.

### Differential / diff-scoped verification
When verifying fixes (or reviewing any change set), scope the deep pass to the diff and its blast radius, not the whole repo every time - but always re-run the relevant custom rules tree-wide so a fix in one file cannot mask an untouched variant elsewhere. Use git history to confirm the fix commit actually touches the root-cause code and did not just edit a comment or a test to make CI pass. A fix commit that only changes test assertions is a red flag.

### Verdict
A finding moves to CLOSED only when ALL hold: root cause addressed, original PoC now fails, obvious bypasses fail, custom rule is clean tree-wide, no fix-introduced variant, regression guard in place. Anything short of all six is REOPEN or PARTIAL, never CLOSED.

---

## Part 4 - Wire it into the engagement (the firm spine)

The four parts above are a loop, not a one-shot. The full audit-firm engagement spine, with this file's loop in its place:

1. **Scope + authorization** (engagement letter / program rules - same gate as bounty workflow step 1).
2. **Context building** - understand the architecture and trust boundaries before hunting (pairs with code-reviewer execution-path tracing; index large repos first).
3. **Hunt** - scanners as triage (scanning-stack.md) + manual attacker reasoning (adversarial-bounty-hunting.md) -> confirmed findings.
4. **THIS LOOP per confirmed finding** - variant analysis -> custom rule -> (client patches) -> fix-verification -> regression rule in CI.
5. **Report** - per-finding using the bounty report structure, PLUS a variants table (the whole class), the custom rule shipped, and the fix-verification verdict.
6. **Retest engagement** - the loop's fix-verification step IS the retest; the custom rules make retests cheap and reproducible on the next release.

The custom rules authored across engagements accumulate into a house ruleset (kept separate from registry rules per the license posture) - the firm's compounding asset and the reason an experienced shop finds the second client's bug faster than the first.

---

## Cross-references
- references/scanning-stack.md - the tool/check catalog. Variant analysis (Part 1) and rule authoring (Part 2) both USE the Semgrep engine named there; fleet checks FA-1/FA-2 are themselves codified detectors in the spirit of Part 2. NO tool list duplicated here.
- references/adversarial-bounty-hunting.md - the per-finding attacker mindset and quality gate that produces the SEED finding this loop operates on. Run that file's gate first; this file is what a firm does after a finding passes it.
- references/trivy-and-dast.md - operational single-scanner runs; the fix-verification re-scan (Part 3 step 4) reuses these invocations.
- rules.md - severity taxonomy and red flags; the fix-verification verdict (CLOSED/REOPEN/PARTIAL) feeds the risk register there.
- code-reviewer references/variant-analysis-and-fix-verification.md - the REVIEW-side mirror of this file (variant + fix-verify applied to PRs/diffs rather than full audits). The two share the methodology; this file is engagement-scale, that file is PR-scale.
- code-reviewer references/codebase-takeover-and-audit.md - silent-failure class (referenced in Part 3 step 5 for fix-introduced swallowed errors) and adversarial verification of the deliverable.

## Memory scope keys
- security-auditor/audit/<client>/seed-findings - confirmed findings that triggered a variant sweep (with root-cause sentence + CWE)
- security-auditor/audit/<client>/variants/<finding-id> - the full sibling class found by variant analysis (file/line/taint/reachability each)
- security-auditor/audit/<client>/custom-rules - rules authored from this client's findings (provenance + TP/TN test cases + CWE); WE-authored, kept separate from registry rules per license posture
- security-auditor/audit/<client>/fix-verification/<finding-id> - per-finding verdict (CLOSED/REOPEN/PARTIAL) + PoC re-run result + bypass attempts + tree-wide rule result
