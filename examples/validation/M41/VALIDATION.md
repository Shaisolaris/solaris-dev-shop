# M41 validation of G41 5042950 (Grok self-validation, not independent review)

Verdict: **PASS with P3 residuals (no P1 or P2)**. The inventory's classification matches an independent
classification of every selected goal against root's acceptance files and the candidate index, the gate is honestly
NOT_READY with true reasons, nothing is applied, and the metadata reconciliation is right. Two contract-level gaps
remain: goals not selected for the week block the gate, and the candidate index it trusts is stale against the remote
review branches. This is Grok checking a Grok build. It is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 50429506620691dc9ddb620f2397b1f3dcd39f67, one commit on G40 r2 0f593a1. G41.patch sha256 6b8296b9...e856
  equals the diff; MANIFEST.sha256 9/9 match and equals the diff set; every file is inside G41's writable scope.
- Prerequisite chain: G40 r2 fails M40 (b3139e1, P2-1) and G39 r2 fails M39 r2 (a4182208, P2-1), and G39 r2 sits on
  superseded G05 and G19 heads. G41 changes none of their files, but its rebase rule will apply when they move.

## Classification against the acceptance files (results/independent-classification.txt)
oracle/m41_classify.py classifies from the documented rules (written from the docstring; I had read only the docstring
and constants of the tool) using copies of WORK-QUEUE.json, ACCEPTANCE-A, -B, -PR and candidate-index.json taken at
11:47 PT (hashes in raw/inputs-sha256.txt; the copies are not published). Live tool run on the same copies with --git:
NOT_READY, exit 1 (results/live-inventory-now.json).
- All 84 selected goals: identical dispositions, 38 accepted, 13 candidate_only, 33 missing; 0 acceptance_stale given
  the index; 0 conflicts; P01 to P04 accepted without a commit as documented.
- Differences: only the 8 goals not selected for the week (G26 to G29, M26 to M29), which the tool lists as missing
  (P3-1).
- Queue status vs acceptance files: no acceptance entry disagrees with the queue's exact_revision. R01 to R04 are
  `accepted` in the queue but have no acceptance-file entry; the tool shows them as missing (P4-1).
- Required final goals G39, M39, G40, M40, G41, M41, G42, M42 are not accepted; the tool names each.

## Gate honesty and nothing applied
- NOT_READY reasons are all true: the candidate_only and missing goals, the eight required final goals, and
  candidate_commit, checks_revision and reviewed_revision unset by root. Exit 1.
- Proposed version 0.62 from 0.61, `applied: false`. The candidate tree's pyproject.toml, CHANGELOG.md, skills.json and
  roster.json equal main 02ba9c5; worktree status 0 lines before and after the live run; only `--out` is written (R05).

## Metadata reconciliation (results/metadata-independent.txt)
Independent count: pyproject 0.61 and top CHANGELOG heading 0.61; description says 61; employees/*/*/SKILL.md 61;
skills.json 61. The tool reports the same with no problems, and R04 shows each kind of disagreement is caught. roster.json
holds 62 capabilities; the tool does not reconcile the roster (root-owned, listed as blocked), and I did not check it.

## Findings
- **P3-1 Goals not selected for the week block the gate.** The docstring says "for every selected goal", but an
  unselected held goal is classified missing and makes the gate NOT_READY (R03; the live run lists all eight unselected
  goals among its reasons). It fails closed, but once every selected goal is accepted the gate still cannot be READY
  without root editing those goals.
- **P3-2 The inventory trusts a candidate index that is stale against the remote review branches.** For 13 goals the
  index candidate differs from the remote review branch head (raw/remote-heads.txt at 11:50 PT). Three are reported
  accepted while their branch carries newer, unreviewed commits: G01 a069a79 to aa0b083, G19 5606672 to 350d175 (G19 h1)
  and G37 9b0f58e to e9b7a77. G39 and G40 rows still point at r1. A release built from those heads would include
  revisions the inventory calls accepted but nobody reviewed. Suggest an optional remote-heads input that turns such
  goals into acceptance_stale, or a refreshed index as a gate input.
- **P4-1** A goal the queue marks accepted with no acceptance record is shown as `missing`, not as a queue/acceptance
  conflict. The gate still names it, so the verdict stays honest.
- **P4-2** The next-version proposal for 1.2.3 is "1.3" (patch dropped); 0.9 gives 0.10 (O06, observation).

No proposed fix: there is no P1 or P2.

## Oracle and results
oracle/m41_oracle.py (written from M41.md, G41.md and the docstring before reading the builder's inventory_oracle.py):
R01 clean READY control, R02 honest NOT_READY (stale candidate, missing acceptance, missing goal, required goal not
accepted or excluded, conflicting acceptances, each unset root revision), R03 selection, R04 metadata, R05 --out and
invalid input, O06 observations. 4/5 on all four Pythons (R03, P3-1). Negative controls: base 0f593a1 without the tool
0/5, builder no-op 0/5, builder naive 2/5. Builder: G41 tests OK, inventory oracle 10/10, naive 5/10, no-op 0/10 on all
four Pythons. Fresh caller: README run block verbatim under env -i on 3.9.6 and 3.13.15, documented results, 0 pycache,
tree unchanged.
The full suite failed one test on 3.9.6 and 3.11.16 under load: test_g19_capability ... test_oracle_accepts_real_api_and_
rejects_stubs, the inherited G19 flake (M39 P4-1) that G19 h1 350d175 fixes and this base does not carry.

## Teeth
Builder G41 mutants (19, unchanged copy): 13/19 killed on 3.13.15 and on 3.9.6. All six survivors are killed by the
builder's tests. My oracle's conflict case does not isolate conflict handling (the conflicting commit also differs from
the index, so the goal is named either way); disclosed as an oracle gap.
- teeth-3.13.15.log: conflicts_ignored SURVIVED
- teeth-3.13.15.log: applied_true SURVIVED
- teeth-3.13.15.log: short_sha_ok SURVIVED
- teeth-3.13.15.log: dup_queue_ok SURVIVED
- teeth-3.13.15.log: git_inverted SURVIVED
- teeth-3.13.15.log: required_outside_queue_ok SURVIVED
- teeth-3.9.6.log: conflicts_ignored SURVIVED
- teeth-3.9.6.log: applied_true SURVIVED
- teeth-3.9.6.log: short_sha_ok SURVIVED
- teeth-3.9.6.log: dup_queue_ok SURVIVED
- teeth-3.9.6.log: git_inverted SURVIVED
- teeth-3.9.6.log: required_outside_queue_ok SURVIVED
- builder tests: conflicts_ignored builder tests: KILL FAILED (failures=1) FAIL: test_naive_rejected (tests.test_g41_capability.Controls.test_naive_rejected)
- builder tests: applied_true builder tests: KILL FAILED (failures=2) FAIL: test_naive_rejected (tests.test_g41_capability.Controls.test_naive_rejected); FAIL: test_o7 (tests.test_g41_capability.OracleChecks.test_o7)
- builder tests: short_sha_ok builder tests: KILL FAILED (failures=2) FAIL: test_naive_rejected (tests.test_g41_capability.Controls.test_naive_rejected); FAIL: test_o9 (tests.test_g41_capability.OracleChecks.test_o9)
- builder tests: dup_queue_ok builder tests: KILL FAILED (failures=2) FAIL: test_naive_rejected (tests.test_g41_capability.Controls.test_naive_rejected); FAIL: test_o9 (tests.test_g41_capability.OracleChecks.test_o9)
- builder tests: git_inverted builder tests: KILL FAILED (failures=1) FAIL: test_o10 (tests.test_g41_capability.OracleChecks.test_o10)
- builder tests: required_outside_queue_ok builder tests: KILL FAILED (failures=1) FAIL: test_required_goal_outside_queue_is_invalid (tests.test_g41_capability.Direct.test_required_goal_outside_queue_is_invalid)

## Disclosures
- No authoring fix to the M41 oracle. The programme input copies are kept unpublished; only their hashes are published.
- Collision check (raw/collision-check.txt); week-grok before and after records; no builder directory touched.

## Pyversions matrix
```
ls: /tmp/m41mx-Px4JnV/build: No such file or directory
== 3.9.6 | g41: OK | full: Ran 331 tests in 144.399s  FAILED (failures=1, skipped=1)  FAIL: test_oracle_accepts_real_api_and_rejects_stubs (test_g19_capability.ProbeAndOracle)  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 5/10 | builder-noop: REJECTED 0/10 | m41-oracle: M41 ORACLE 4/5 scored FAIL | pycache in copy: 0 | build/egg-info in copy: 0
== 3.11.16 | g41: OK | full: Ran 331 tests in 135.858s  FAILED (failures=1)  FAIL: test_oracle_accepts_real_api_and_rejects_stubs (test_g19_capability.ProbeAndOracle.test_oracle_accepts_real_api_and_rejects_stubs)  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 5/10 | builder-noop: REJECTED 0/10 | m41-oracle: M41 ORACLE 4/5 scored FAIL | pycache in copy: 0 | build/egg-info in copy: 2
== 3.12.14 | g41: OK | full: Ran 331 tests in 170.075s  OK   | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 5/10 | builder-noop: REJECTED 0/10 | m41-oracle: M41 ORACLE 4/5 scored FAIL | pycache in copy: 0 | build/egg-info in copy: 2
== 3.13.15 | g41: OK | full: Ran 331 tests in 150.814s  OK   | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 5/10 | builder-noop: REJECTED 0/10 | m41-oracle: M41 ORACLE 4/5 scored FAIL | pycache in copy: 0 | build/egg-info in copy: 2
candidate status lines: 0
```
