# M39 r2 validation of G39 r2 05378c4 (Grok self-validation, not independent review)

Verdict: **FAIL (one P2)**. Root's contract for G39 (ROOT-FINDINGS.json item 8: "bind explicit and indirect inputs plus
complete output membership and honest exit/gap verdicts") is met for indirect inputs declared with `--inputs`, for
output-folder membership and for exit 2 at record time, but not for explicit inputs named in the command in four common
spellings. This is Grok checking a Grok build. It is not independent review and accepts nothing.

## Own-patch disclosure
The G39 r2 fixes generalise my own M39 proposed-fix.patch (M39 62400ee). I am validating a repair that came from my
patch, so I wrote a new contract oracle from root's wording instead of relying on my M39 oracle, and I probed the
places my patch did not reach.

## Binding (raw/binding-verify.txt)
- Candidate 05378c4ed33525e4c1dcafdfd0a2bb01506f9c6e, parent G39 r1 f04d34d (fast-forward), whose parent is fabed6a.
- G39-r2.patch sha256 4e6d66da...dba44 equals `git diff --binary f04d34d 05378c4`; MANIFEST.sha256 11/11 match, and the
  manifest set equals the diff set.
- Evaluated in a detached worktree /tmp/m39r2-eval and rsync copies; the candidate was never modified.

## Prerequisite chain (P3-4, superseded prerequisites)
The integration base fabed6a carries G05 8b38a72 and G19 5606672. Both have newer heads on the remote
(raw/prerequisite-heads.txt):
- G05 r2 3056378 (10:45 PT, after this candidate's 10:40 PT commit) changes quality_os.py, which delivery_evidence.py
  loads for artifact_digests and binding_state.
- G19 h1 350d175 (10:54 PT) fixes the oracle stop() race that I traced in M39 (P4-1). That inherited flake failed the
  full suite here on 3.9.6, 3.12.14 and 3.13.15 under load (pyversions matrix below); 3.11.16 passed.
The handback's rebase rule now applies. Rebase rehearsal on a scratch copy (results/rebase-rehearsal.txt): G39 r2 plus
the G05 r2 and G19 h1 deltas, G39 + G05 closure + G19 tests OK, drill passed, drill_oracle 18/18, M39 oracle 8/9 (the
same sub as below). G02 and G04 also have newer heads but are not in fabed6a.

## Root contract, item by item
| Contract part | Result | Evidence |
|---|---|---|
| Explicit inputs bound | **partial (P2-1)** | C01: positional and `--flag VALUE` bound; `--flag=VALUE`, a folder, an absolute path inside ROOT, a symlink not bound |
| Indirect inputs bound | pass when declared with `--inputs` | C02 13/13 subs; undeclared indirect inputs stay unbound (documented limit, Q05) |
| Output-folder membership | pass | C03 9/9 subs: removed, renamed, added, nested add, swapped, symlink swap, folder deleted or emptied, restore |
| Exit 2 never counts as GO | pass at record time; P3-1 for a rewritten record | C04 12/12 subs: `--ok-exit` with 2, 3, 255 or without 0 refused before running; tool exit 2 never counts, even with accept_gaps |
| Honest exit and gap verdicts | verdict word honest; P3-3 for exit codes | C04 exit 1 never plain GO; Q05 verify exit 0 for GO_WITH_GAPS and EVIDENCED_NO_ORDER |

## Findings
- **P2-1 Explicit command-line inputs in four common spellings are silently unbound.** `_named_inputs` skips every
  argument that starts with `-`, keeps only regular files, and drops absolute paths and symlinks. So
  `--src=inp/a.csv`, a folder argument (`inp`), an absolute path inside ROOT, and a symlink named in the command give
  `claimed_inputs: []`; changing the file afterwards still gives **GO**. results/probe-applied.txt shows the reader
  really reads each input (its output changes when re-run). Same on all four Pythons. A real case: a snapshot tool
  called as `snapshot db --out ...` with `db` a folder. Negative control: r1 f04d34d scores 0/4 on the contract oracle.
- **P3-1 A record that says exit 2 and ok true still gives GO.** verify trusts the stored `ok` flag; a consistent full
  rewrite (documented as not caught for the chain) with `exit: 2, ok_exit: [0,1,2], ok: true` is **GO** (Q05). verify
  could recheck `exit in ok_exit` and `ok_exit` within {0,1} at no cost, so exit 2 never counts whatever the record says.
- **P3-2 An input the run rewrote is bound to its after-run digest and the verdict is plain GO.** It is listed only in the
  record's `inputs_changed_during_run`; verify neither shows it as a gap nor blocks (Q05).
- **P3-3 verify exits 0 for GO, GO_WITH_GAPS and EVIDENCED_NO_ORDER.** Documented (open question 1). A caller that gates
  on the exit code ships a delivery with accepted gaps or with no work order. Suggest distinct non-zero exits (for
  example 0 GO, 3 GO_WITH_GAPS, 4 EVIDENCED_NO_ORDER) or a `--strict` flag.
- **P3-4 Superseded prerequisites** (section above).
- OBS: an empty subfolder added to an input or output folder keeps GO (no content changed; fine). An imported helper
  module or an undeclared file the tool reads stays unbound unless listed in `--inputs` (documented limit).

## Proposed fix (P2-1 and P3-1; not applied)
proposed-fix.patch (delivery_evidence.py only): `--flag=VALUE` names VALUE; absolute paths inside ROOT are relativised;
folders are bound; a symlink named in the command is refused (exit 2), like `--inputs`; `.` and outputs are skipped;
verify treats a record whose exit is not in its ok_exit, or whose ok_exit is not within {0,1}, as failed.
Positive control (results/fix-positive-control.txt): applies cleanly to 05378c4; contract oracle 4/4 and the rewritten
exit-2 record NO_GO; M39 oracle 8/9 (same sub); builder G39 tests OK, drill passed and drill_oracle 18/18 on 3.13.15
and 3.9.6. Applied only to a copy, never to the candidate.

## Oracles and results
- oracle/m39r2_contract.py (new, rows C01 to C04 scored, Q05 observations), written from root's contract and the r2 doc.
  It reuses the M39 oracle's Box helpers unchanged. 3/4 on all four Pythons; naive 2/4; r1 negative control 0/4.
- oracle/m39_oracle.py: the M39 oracle copied unchanged. 8/9 on all four Pythons; naive 4/9, no-op 0/10. The only failing
  sub is D02 head_lag_one_tolerated_and_repaired: r2 now treats a head lagging by one as unconfirmed (NO_GO until the
  next append), which is exactly what M39 P3-2 asked for. Not a finding. I did not edit the oracle to match.
- Builder: G39 tests 42 OK, drill passed, drill_oracle 18/18, naive 12/18, no-op 0/18 on all four Pythons.
- Fresh caller (results/fresh-caller.txt): README run block verbatim under env -i with a new HOME on 3.9.6 and 3.13.15,
  every line gives its documented result; 0 pycache; tree unchanged.

## Teeth
Builder G39 r2 mutants (60, unchanged copy) scored by oracle/m39r2_all.py (both oracles): 49/60 killed on 3.13.15, 48/60
on 3.9.6. The survivors exercise r2 behaviour that my oracles record only as observations (log digest, no-order,
intake, deleted or emptied ledger, accept_gaps type). The builder's tests kill every survivor except
r2_missing_input_ok, which is equivalent (artifact_digests also refuses a missing path, still exit 2, which C02 checks).
That is a gap in my oracle, disclosed, not in the candidate.
- teeth-3.13.15.log: broken_chain_trusted SURVIVED
- teeth-3.13.15.log: head_lag_never SURVIVED
- teeth-3.13.15.log: r2_inputs_before_run SURVIVED
- teeth-3.13.15.log: r2_missing_input_ok SURVIVED
- teeth-3.13.15.log: r2_accept_gaps_type_unchecked SURVIVED
- teeth-3.13.15.log: r2_log_unchecked SURVIVED
- teeth-3.13.15.log: r2_log_digest_unchecked SURVIVED
- teeth-3.13.15.log: r2_no_order_go SURVIVED
- teeth-3.13.15.log: r2_intake_unchecked SURVIVED
- teeth-3.13.15.log: r2_deleted_ledger_fresh SURVIVED
- teeth-3.13.15.log: r2_emptied_ledger_ok SURVIVED
- teeth-3.9.6.log: broken_chain_trusted SURVIVED
- teeth-3.9.6.log: bytecode_written SURVIVED
- teeth-3.9.6.log: head_lag_never SURVIVED
- teeth-3.9.6.log: r2_inputs_before_run SURVIVED
- teeth-3.9.6.log: r2_missing_input_ok SURVIVED
- teeth-3.9.6.log: r2_accept_gaps_type_unchecked SURVIVED
- teeth-3.9.6.log: r2_log_unchecked SURVIVED
- teeth-3.9.6.log: r2_log_digest_unchecked SURVIVED
- teeth-3.9.6.log: r2_no_order_go SURVIVED
- teeth-3.9.6.log: r2_intake_unchecked SURVIVED
- teeth-3.9.6.log: r2_deleted_ledger_fresh SURVIVED
- teeth-3.9.6.log: r2_emptied_ledger_ok SURVIVED
- builder tests: broken_chain_trusted builder tests: KILL FAILED (failures=1) FAIL: test_broken_ledger_refuses_before_running_the_command (tests.test_g39_capability.Direct.test_broken_ledger_refuses_before_running_the_command)
- builder tests: head_lag_never builder tests: KILL FAILED (failures=2) FAIL: test_head_lagging_one_record_is_tolerated_but_not_two (tests.test_g39_capability.Direct.test_head_lagging_one_record_is_tolerated_but_not_two); FAIL: test_o17_unconfirmed_and_log (tests.test_g39_capability.OracleChecks.test_o17_unconfirmed_and_log)
- builder tests: r2_inputs_before_run builder tests: KILL FAILED (failures=1) FAIL: test_input_rewritten_by_the_run_is_noted_and_bound_after (tests.test_g39_capability.Direct.test_input_rewritten_by_the_run_is_noted_and_bound_after)
- builder tests: r2_missing_input_ok builder tests: no kill OK
- builder tests: r2_accept_gaps_type_unchecked builder tests: KILL FAILED (failures=1) FAIL: test_exit_1_is_evidenced_with_gaps_and_needs_the_claim (tests.test_g39_capability.Direct.test_exit_1_is_evidenced_with_gaps_and_needs_the_claim)
- builder tests: r2_log_unchecked builder tests: KILL FAILED (failures=2) FAIL: test_log_changed_or_removed_is_log_mismatch (tests.test_g39_capability.Direct.test_log_changed_or_removed_is_log_mismatch); FAIL: test_o17_unconfirmed_and_log (tests.test_g39_capability.OracleChecks.test_o17_unconfirmed_and_log)
- builder tests: r2_log_digest_unchecked builder tests: KILL FAILED (failures=1) FAIL: test_log_changed_or_removed_is_log_mismatch (tests.test_g39_capability.Direct.test_log_changed_or_removed_is_log_mismatch)
- builder tests: r2_no_order_go builder tests: KILL FAILED (failures=2) FAIL: test_no_order_claim_is_never_go_and_bad_order_path_refused (tests.test_g39_capability.Direct.test_no_order_claim_is_never_go_and_bad_order_path_refused); FAIL: test_o18_order_intake_ledger (tests.test_g39_capability.OracleChecks.test_o18_order_intake_ledger)
- builder tests: r2_intake_unchecked builder tests: KILL FAILED (failures=1) FAIL: test_o18_order_intake_ledger (tests.test_g39_capability.OracleChecks.test_o18_order_intake_ledger)
- builder tests: r2_deleted_ledger_fresh builder tests: KILL FAILED (failures=2) FAIL: test_emptied_or_deleted_ledger_with_head_is_broken (tests.test_g39_capability.Direct.test_emptied_or_deleted_ledger_with_head_is_broken); FAIL: test_o18_order_intake_ledger (tests.test_g39_capability.OracleChecks.test_o18_order_intake_ledger)
- builder tests: r2_emptied_ledger_ok builder tests: KILL FAILED (failures=1) FAIL: test_emptied_or_deleted_ledger_with_head_is_broken (tests.test_g39_capability.Direct.test_emptied_or_deleted_ledger_with_head_is_broken)
- builder tests: bytecode_written (3.9.6 only) builder tests: not rerun on 3.9; the Apple 3.9.6 interpreter never writes bytecode, and the mutant is killed by this oracle on 3.13.15 (same as M39)

## Disclosures
- One authoring fix in m39r2_contract.py before any teeth run: the default reader claim file was never written, so every
  first-run verify exited 2. Fixed by writing it in the helper constructor (marked in the source).
- The M39 oracle was not changed. Oracle hashes at teeth start are in results/oracle-sha-at-teeth-start.txt.
- Collision check (raw/collision-check.txt); week-grok before and after records; no builder directory touched.

## Pyversions matrix
```
== 3.9.6 | m39r2-contract: M39R2 CONTRACT 3/4 core FAIL | contract-naive: M39R2 CONTRACT 2/4 core FAIL | g39: Ran 42 tests in 28.084s  OK  | full: Ran 301 tests in 100.456s  FAILED (failures=1)  FAIL: test_oracle_accepts_real_api_and_rejects_stubs (test_g19_capability.ProbeAndOracle)  | drill: DRILL PASSED | builder-oracle: ACCEPTED 18/18 | builder-naive: REJECTED 12/18 | builder-noop: REJECTED 0/18 | m39-oracle: M39 ORACLE 8/9 core FAIL | m39-naive: M39 ORACLE 4/9 core FAIL | m39-noop: M39 ORACLE 0/10 core FAIL
== 3.11.16 | m39r2-contract: M39R2 CONTRACT 3/4 core FAIL | contract-naive: M39R2 CONTRACT 2/4 core FAIL | g39: Ran 42 tests in 28.163s  OK  | full: Ran 301 tests in 168.793s  OK   | drill: DRILL PASSED | builder-oracle: ACCEPTED 18/18 | builder-naive: REJECTED 12/18 | builder-noop: REJECTED 0/18 | m39-oracle: M39 ORACLE 8/9 core FAIL | m39-naive: M39 ORACLE 4/9 core FAIL | m39-noop: M39 ORACLE 0/10 core FAIL
== 3.12.14 | m39r2-contract: M39R2 CONTRACT 3/4 core FAIL | contract-naive: M39R2 CONTRACT 2/4 core FAIL | g39: Ran 42 tests in 28.319s  OK  | full: Ran 301 tests in 88.512s  FAILED (failures=1)  FAIL: test_oracle_accepts_real_api_and_rejects_stubs (test_g19_capability.ProbeAndOracle.test_oracle_accepts_real_api_and_rejects_stubs)  | drill: DRILL PASSED | builder-oracle: ACCEPTED 18/18 | builder-naive: REJECTED 12/18 | builder-noop: REJECTED 0/18 | m39-oracle: M39 ORACLE 8/9 core FAIL | m39-naive: M39 ORACLE 4/9 core FAIL | m39-noop: M39 ORACLE 0/10 core FAIL
== 3.13.15 | m39r2-contract: M39R2 CONTRACT 3/4 core FAIL | contract-naive: M39R2 CONTRACT 2/4 core FAIL | g39: Ran 42 tests in 28.664s  OK  | full: Ran 301 tests in 86.555s  FAILED (failures=1)  FAIL: test_oracle_accepts_real_api_and_rejects_stubs (test_g19_capability.ProbeAndOracle.test_oracle_accepts_real_api_and_rejects_stubs)  | drill: DRILL PASSED | builder-oracle: ACCEPTED 18/18 | builder-naive: REJECTED 12/18 | builder-noop: REJECTED 0/18 | m39-oracle: M39 ORACLE 8/9 core FAIL | m39-naive: M39 ORACLE 4/9 core FAIL | m39-noop: M39 ORACLE 0/10 core FAIL
pycache in copy: 0
candidate status lines: 0
```
