# M04 validation of G04 (Grok self-validation, NOT independent review)

Grok self-validation by the same bot that built G04. This is not independent review and not manager acceptance.

- Candidate: G04 `314b4dbf980437cf14bc32438117e5b5b777f942` on `review/grok-g04-handoff`. main stays at 02ba9c5.
- Window: 00:35 to 00:46 PT, 2026-10-19. Interpreters 3.9.6, 3.11.16, 3.12.14, 3.13.15. The candidate was checked out as a detached scratch worktree and was not modified.

## Verdict
PASS with residuals. No P1 or P2. One P3 (an owner conflict is not detected) and one P4.

## Prerequisites (raw/fetch-prereq.txt)
- The handback states one prerequisite: G02 at `bbe682b28e96296723826c1f113e138ccc39c530`. The candidate's parent is exactly that commit, and main..candidate is 4113204 (G02), bbe682b (G02 rework) and 314b4db.
- Not superseded: the head of `review/grok-g02-activation` is still bbe682b at 00:35 PT.
- Validation status of the prerequisite: my own M02 pass judged 4113204, not bbe682b. The handback relays that bbe682b scored M02 oracle 11/11 with a Muse direct ACCEPT (owner's 12:13 AM dependency decision). I have not re-validated bbe682b, and I am relaying that claim, not confirming it.

## Disclosures
- Builder and validator are both Grok.
- I built my oracle (`oracle/m04_oracle.py`) after G04 landed, from M04.md, G04.md and the shipped doc `handoff-work-orders.md`. It uses its own order WO-KITE-7 and its own intake text, not the builder's oracle or fixtures. It is black box: only the documented CLI.
- The teeth use the BUILDER's 34 mutants (`oracle/builder_mutants_g04.py`, copied unchanged), scored by my oracle.
- Oracle v2 added the OBS rows C02b and C14b after the first run to adjudicate C02 and C14. Neither row is re-scored.
- Oracle v3 makes file reads tolerate a tool that writes nothing. The noop control crashed v2; that log is kept as `results/control-noop-v2-harness-crash.txt`.
- The fresh caller places the README's `/tmp/g04-demo` under its fresh folder.
- No installs, no network, no paid calls.

## Results
| Check | Result |
|---|---|
| Binding (raw/binding-verify.txt) | `git diff --binary bbe682b 314b4db` is byte-identical to G04.patch (sha256 f44bbe52...). MANIFEST has 16/16 OK, and the manifest set equals the diff set (16 files, +1174/-4) |
| Builder suite, 4 interpreters | G04 13 tests OK; full suite 144 OK; builder oracle 16/16 at scale 200 (8.7 to 9.2 s) |
| Builder controls (3.9.6) | naive 9/16, noop 1/16, as the handback says |
| Grok oracle, 4 interpreters | 14/16 scored rows, the same on all 4. Outputs are identical apart from temp names and C15's timing-dependent split of exits 0 and 4. The 2 FAILs are adjudicated below |
| Grok oracle controls | naive 7/16 (fails C02 C03 C05 C08 C09 C10 C14 C15 C17), noop 0/16 |
| Fresh caller (3.9.6, 3.13.15) | env -i, new HOME, python3 shim, offline guard, README "Try it" commands only. Exits 75, 0 ("duplicate suppressed"), 0; ledger 1; rev2 0 with superseded note; rev1 2; ledger 2. No pycache left |
| Teeth (3.9.6) | My oracle kills 22/34. All 10 survivors not marked EQUIV fail a builder test, so they are non-equivalent and the gaps are in MY oracle. See results/teeth-tally.txt and results/survivors-builder-tests.txt |
| week-grok before and after | identical: head 02ba9c5, index c28a2f586b3e3001, status ab0ce7884ab30372, 95 lines (00:35:38 and 00:43:43 PT) |

My oracle rows:
- C01: clean control.
- C02: handoff after brief.
- C03: crash after the delivery effect.
- C04: status shows pending after a crash.
- C05: replays.
- C06: missing brief.
- C07: edited brief.
- C08: intake edited without a new revision.
- C09: fresh order with a mismatching intake.
- C10: revision 2 supersedes 1, and revision 1 is refused.
- C11: 12 invalid orders.
- C12: edited journal.
- C13: torn journal tail.
- C14: another order's journal.
- C15: 8 concurrent workers.
- C17: a crash drill at each step.
- OBS rows: C06b, C07b, C10b and C16 (owner conflict).

## Adjudications (open, not re-scored)
- **C02 FAIL is my error.** My "earlier files untouched" check counted the runner's bookkeeping file `.handoff/<order>/holder.json` as an earlier output. C02b shows it is the only changed file. The activate and brief outputs were untouched, ben finished the order and the ledger has 1 line.
- **C14 FAIL is a real, minor deviation (P4-1).** The exit is 2 as documented, but the run creates `.handoff/WO-KITE-8/.worker.lock`, while the doc says "Nothing runs and nothing is written" (C14b). The file is an empty lock file and there is no effect.

## Findings by severity
- P1: none. P2: none.
- **P3 (owner conflict not detected; M04 names "conflicting owners").**
  - What happens: the same order and revision is re-issued with a different `owner` after the brief was written. The run exits 0, reuses ana's activate and brief receipts and delivers.
  - The ledger record names the new owner ("support: Someone Else"), but the delivered brief still says "- Owner: delivery-lead: K. Tester" (`results/owner-probe-3.9.6.txt`).
  - Why: the brief embeds the owner, but the owner is not among the brief's receipt inputs (intake and STATUS.md hashes only), so stale evidence is reused.
  - The doc requires a new revision for an intake change but says nothing about owner changes.
  - Suggested direction (not a patch; patches are only required for P1 or P2): either add the owner to the brief's receipt inputs, or refuse an owner change within a revision with exit 2, as for the intake.
- **P4-1:** an exit-2 refusal on a journal from another order writes `.worker.lock` (see C14).
- Observation: receipt_any_rev_EQUIV is behaviour-equivalent (same exits, ledger and files) but not output-equivalent. On revision 2 it prints an extra "activate receipt is stale (inputs changed)" note.
- Observation (my oracle, not the candidate): 10 builder mutants survive my oracle: strict_keys_off, brief_no_owner, inputs_extra_ok, key_no_revision, status_no_stale, fail_record_skipped, chain_unchecked, activate_fail_ignored, ledger_torn_glued and inputs_unchecked. The builder's tests kill each of them.
- Strengths: across 3 crash points and 8 concurrent workers there is exactly one delivery per revision. An edited intake, a stale revision, an edited journal and 12 invalid orders are each refused with nothing written (apart from P4-1). A missing or edited brief is redone without a second delivery.

## Not run
- Workers on other machines or a network folder (locks are local fcntl).
- A router or scheduler launching workers, Hermes jobs, and any live delivery.
- Signal-kill of a running worker (only the documented `--fail-at` drill).
- Large real projects.
- Teeth were run on 3.9.6 only.
