# M05 validation of G05 (Grok self-validation, NOT independent review)

Grok self-validation by the same bot that built G05. This is not independent review and not manager acceptance.

- Candidate: G05 `8b38a72f2183ad7427594d6557d7e308baf0469b` on `review/grok-g05-revision-bound-evidence`. I resolved the full SHA through the GitHub commits API. main stays at 02ba9c5.
- Window: 00:46 to 00:57 PT, 2026-10-19. Interpreters 3.9.6, 3.11.16, 3.12.14, 3.13.15. The candidate was checked out as a detached scratch worktree and was not modified.

## Verdict
PASS with residuals. No P1 or P2. One P3 (waiver-closed findings) and one P4.

## Prerequisites (raw/fetch-prereq.txt)
- The handback states: G04 `314b4dbf980437cf14bc32438117e5b5b777f942`, itself on G02 `bbe682b28e96296723826c1f113e138ccc39c530`.
- The candidate's parent is exactly 314b4db, and 314b4db's parent is exactly bbe682b. main..candidate is 4113204, bbe682b, 314b4db, 8b38a72.
- Not superseded: both branch heads (review/grok-g04-handoff and review/grok-g02-activation) still point at the stated commits at 00:46 PT.
- Validation status of the prerequisites:
  - G04 314b4db: Grok M04 gave PASS with residuals (a P3 owner conflict and a P4), commit 1628e6da79a11b5e00830e574cfa4bf457cc7e61. G05 does not import G04 or G02, so that P3 does not reach G05's code.
  - G02 bbe682b: the G04 handback relays a Muse ACCEPT. I have not re-validated it.

## Disclosures
- Builder and validator are both Grok.
- I built my oracle (`oracle/m05_oracle.py`) after G05 landed, from M05.md, G05.md and ASSURANCE.md "Revision binding". It uses its own two-revision project and roles, not the builder's oracle or fixtures. Packets and digests go through the documented CLI (`run`, `digest`, `self-test`). Closures, reopen and waivers go through the documented API.
- Teeth use the BUILDER's 40 mutants (`oracle/builder_mutants_g05.py`, copied unchanged), scored by my oracle.
- Harness fixes during the pass, with the bad runs kept where they ran:
  - v1 crashed loading the engine module before any closure row ran.
  - v2 used severity "high" where the engine expects S0 to S4, so every closure row returned INVALID_FINDING and tested nothing (`results/oracle-v2-first-run-3.9.6.txt`). v3 uses S2. That was an input error in my harness, not an expectation change.
  - v4 guards the API block, so the noop control fails those rows instead of crashing.
  - OBS rows C06b and C17c were added after the v2 run. C06 is not re-scored.
  - v3 results are kept in `results/oracle-v3/`.
- No installs, no network, no paid calls.

## Results
| Check | Result |
|---|---|
| Binding (raw/binding-verify.txt) | `git diff --binary 314b4db 8b38a72` is byte-identical to G05.patch (sha256 0c3e6386...). MANIFEST has 20/20 OK, and the manifest set equals the diff set (20 files, +1088/-4) |
| Builder suite, 4 interpreters | G05 11 tests OK; full suite 155 OK; builder oracle 16/16 |
| Grok oracle, 4 interpreters | 19/20 scored rows, identical on all 4 (apart from C11's timing). The 1 FAIL (C06) is adjudicated below |
| Grok oracle controls | naive (binding stripped) 6/20; noop 1/20 |
| Fresh caller (3.9.6, 3.13.15) | env -i, new HOME, python3 shim, offline guard, only the README and ASSURANCE.md commands. digest exit 0, self-test 0, route 0; builder oracle 16/16, naive 6/16, noop 3/16; no pycache |
| Teeth on **3.9.6 and 3.13.15** | My oracle kills 30/40 on both, with identical per-mutant kill sets. All 8 survivors not marked EQUIV fail a builder test. The 2 EQUIV mutants survive both (results/teeth-tally.txt, survivors-builder-tests.txt) |
| week-grok before and after | identical: head 02ba9c5, index c28a2f586b3e3001, status ab0ce7884ab30372, 95 lines (00:46:30 and 00:54:53 PT) |

How my rows map to the M05 challenges:

| M05 challenge | Rows |
|---|---|
| Changed artifact after a pass | C02: subject r2 with r1 receipts. Security and functional go stale (STALE_GATE_EVIDENCE, the action names the gate and r2, the changed file is app/login.py) and ux carries forward |
| Changed content under the same revision label | C03 |
| A valid reviewed revision stays acceptable | C04: full and 7-character ids |
| Corrected retry | C05: re-run only the stale gates; C16: re-close at r2 with new evidence |
| Unbound receipt | C07 |
| Contradictory receipts | C08: REVISION_CONFLICT, while agreeing receipts pass |
| Legacy shape unchanged | C00 and C09 |
| Malformed requests fail boundedly | C10: 25 malformed bindings, including 10001 paths. All are INVALID_PACKET or INVALID_GATE_EVIDENCE, with under 4000 characters of output |
| Scale | C11: a 10000-path subject in 0.14 s |
| `digest` | C12: matches hashlib and is usable as a subject. C13: exit 2 for escape, symlink, symlink inside a folder, missing, empty, bad revision, over 64 MiB and absolute paths |
| Closure binding | C14: current, STALE_CLOSURE_EVIDENCE, MISSING_VERIFIED_REVISION, INVALID_REVISION, abbreviated ids |
| Independent versus self-approval | C15: SELF_APPROVAL_FORBIDDEN and NON_INDEPENDENT_CLOSURE_EVIDENCE |
| Closure goes stale, reopen, retry | C16: close at r1, STALE_CLOSURE at r2, reopen (short reason refused), old evidence refused, new evidence accepted, UNBOUND_CLOSURE, NOT_CLOSED |
| Revoked or expired waiver | C17: a valid waiver works at any revision; expired, revoked and self-approved waivers are refused |
| CLI closure fixture | C18 |
| Self-test | C19 |

## Adjudication (open, not re-scored)
- C06 FAIL: I sent `reviewed.digests: {}` (an empty map) and expected "stale, revisions differ without digest cover". The engine rejects an empty digests map as malformed (INVALID_GATE_EVIDENCE), which still fails closed.
- C06b, the actual case (a different revision with no `digests` key), is stale as documented. The doc does not say digests must be nonempty; see P4-1.

## Findings by severity
- P1: none. P2: none.
- **P3 (waiver semantics, which G05 must preserve).** The doc says "a valid waiver closes a waived finding at any revision until it expires, and `reopen_finding` does not apply to waived findings." In practice (C17c):
  - Closing a waived finding through a valid waiver sets status "closed" and leaves `closed_at_revision` empty.
  - `closure_is_current` then reports UNBOUND_CLOSURE at every revision.
  - `reopen_finding` reopens it, because it checks only `status == "closed"`.
  - So a caller following the documented loop (check `closure_is_current`, reopen when it is not current) would reopen a finding whose waiver is still valid.
  - The effect is conservative (more work, not a silent pass), but it contradicts the documented waiver semantics.
  - Suggested direction (not a patch; patches are only required for P1 or P2): treat a closure with `waiver_id` set as waiver-governed in both functions.
- **P4-1:** an empty `digests` map is rejected as malformed, while the doc's state table implies "no digest cover" would be stale or unbound. The doc should say digests must be nonempty.
- Observation (my oracle, not the candidate): 8 builder mutants survive my oracle: carry_any_digest, conflict_exact, digest_symlink_ok, empty_binding_ok, extra_keys_ok, fixture_rev_untyped, prefix_any_length and reopen_any_status. The builder's tests kill each of them. digest_symlink_ok survives my symlink rows because the escape check also catches them.
- Strengths: every M05 challenge listed in the table behaves as documented. Malformed input is bounded. Packets without binding are unchanged.

## Not run
- Whether a reviewer really examined the named revision (receipts are declarations).
- git itself (callers supply revisions and digests).
- Real release packets.
- Concurrency (the engine is a pure function plus a read-only digest).
- Teeth on 3.11.16 and 3.12.14 (run on 3.9.6 and 3.13.15 only).
