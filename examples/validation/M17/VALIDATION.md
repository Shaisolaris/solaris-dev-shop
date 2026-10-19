# M17 validation of G17 (leadership decisions with real domain oracles)

**Grok self-validation, not independent review.** The same operator family built G17 and wrote this check. M17.md
names Muse as owner; this pass does not stand in for Muse's review.

## Binding
- Candidate: `550f1848a76ad4d5b6688090afc0519354ac3370` (review/grok-g17-resource-decision), parent
  `6f7b23aa18413907c5fbd250daab475dc94e7a1e` (G14 r2, validated by M14 r2 60682d2). main 02ba9c5 and G13 r3
  5666e7b unchanged. Nothing in the chain is superseded.
- Handback patch sha256 0e5a3646...c385 equals the candidate diff; manifest 24/24 entries, 0 mismatches, manifest
  set equals diff set (raw/binding-verify.txt).
- Everything ran on rsync copies of a detached worktree at 550f184. The candidate was never modified; the
  week-grok record and listing are identical before and after (raw/weekgrok-before.txt, raw/weekgrok-after.txt).

## Verdict: PASS with one P4 residual
Impossible schedules are rejected with their cause (capacity with exact short hours, dependencies, sequencing) and
narrowed where the doc says so; assumptions carry source, date and range; every figure reruns (`verify`) and a
tampered figure is named; no certainty language, the owner decides, nothing is sent.

| id | severity | finding |
|---|---|---|
| P4-1 | P4 | Handback metadata: it names the prerequisite branch `review/grok-g14-cash-revenue-reconcile`; the remote branch is `review/grok-g14-cash-revenue`. The SHA 6f7b23a is right, so binding is unaffected. |

Recorded, not graded (doc-consistent; the builder's open questions):
- Buffer basis: the buffer is months of the outflow in force that week, so a contractor's own cost raises it
  (studio contractors breach in week 17 at 304,692.31 < 308,000.00). This is what the doc says; a board policy
  on base outflow only would be a contract change, not a defect.
- `feasible_irreversible_only` exits 0 (doc: 0 when at least one option is feasible in the downside). Q08 checks
  the status string; a caller keying on the exit code alone cannot tell it from `feasible_options`.
- O09b: risk_exposure lists the base probability and base extra hours (0.25 x 26,000 = 6,500.00 expected cost);
  the downside realises the high bound in full. Doc: probabilities only weight the listed exposure.
- O10b: an assumption with low above high is refused (exit 2).
- O04c: the sequencing cause is named in words ("enough backend hours in total by week 16, but ...").

## Oracle (oracle/m17_oracle.py, v2, 30 core rows plus 3 OBS)
Written from M17.md and resource-cash-decision.md only. An independent week-by-week model of the documented rules
(per-role priority list scheduling with max_people caps, start the week after dependencies, adverse bounds or
the stated downside, risks realised in the downside, weekly cash = monthly x 12/52 in exact fractions, buffer =
months x outflow in force, first week below it) gives expected finish weeks, feasibility, cause, cash figures
and ordering; rows compare them field by field for every option and case. Covers: clean control; capacity
infeasibility with exact short hours and the earliest narrowed week; a dependency chain that ten people cannot
beat; optional work first in priority (sequencing) narrowed by dropping it; contractor cash breach with the
exact week and cash named as binding; one consistent downside world; reversible-first then lowest-cash
ordering; irreversible-only status; realised risk; 6 invalid packages (future-dated, literal number, no owner,
cycle, unknown assumption, unsourced) exit 2 with nothing written; contradictory stakeholder inputs (one start
date driving a later capacity start and an earlier cost start with no stated downside is refused; a stated
downside is used for both; a value outside its own range is refused); a contractor's until_week; dissent echoed;
stale and unranged figures named as required evidence; evaluate --out then verify, a tampered figure named,
--out onto the package refused; recovery by the narrowed deadline shift; the deadline boundary week; G14
evidence gate (unreconciled books block, exit 1) and G14 monthly scaling (108,000 in 30 days = 109,500); a
25-package property test.

Disclosed oracle evolution: four authoring errors in my own rows were fixed before any scoring run against
the controls (Q01 and Q12 deadlines my own model called infeasible; Q04 deadline; Q07b expected list not
filtered to feasible options); that first run is kept at results/kept/oracle-authoring-run-3.9.6.json. v1 (25
rows) teeth on 3.13.15 were 30/37; the survivors (source_optional, conflict_ok, until_ignored,
cash_not_binding, unranged_not_required, out_overwrites_pkg, g14_period_unscaled) pointed at doc rules v1 never
exercised, so v2 added Q05b, Q10 unsourced, Q17a-c, Q19, Q21, Q22, Q23. v1 oracle and results are kept
(oracle/m17_oracle_v1.py, results/v1). The Q12 harness was also made to survive a stub that writes no report.

## Matrix (results/pyversions-matrix.txt), same on 3.9.6, 3.11.16, 3.12.14, 3.13.15
- tests.test_g17_capability 15 OK; full suite 149 OK.
- Builder oracle ACCEPTED 12/12; naive REJECTED 1/12; noop REJECTED 1/12.
- M17 oracle 30/30; naive control 0/30; noop control 0/30.
- No __pycache__ left in the copy; candidate status clean.

## Mutation tests (builder's 37 G17 mutants copied unchanged, scripts/builder_mutants_g17.py)
Kill = any core result or OBS detail change against the unmutated baseline.
- 3.13.15: 37/37. 3.9.6: 37/37. No survivors.

## Fresh caller (results/fresh-caller.txt)
README demo verbatim under env -i with a new HOME on 3.9.6 and 3.13.15: evaluate exit 0 in text and JSON; status
feasible_options with only descope-reporting feasible in the downside; the README's hand-worked figures all match
(as-is short 73.2 backend hours, finishes week 18, closing 337,000.00; contractors breach week 17 304,692.31 <
308,000.00; hire 8.4 hours short and week 18 315,769.23 < 316,000.00). Builder oracle 12/12, naive 1/12, noop
1/12. The README's unreconciled-books claim, run here: blocked_evidence, exit 1. Tree byte-identical, no
__pycache__. The only HOME entry on 3.9.6 is Apple Python's own Library/Caches/com.apple.python.

## Not done
No real company books or decisions were used (all synthetic); no M2, promotion, PR or merge.
