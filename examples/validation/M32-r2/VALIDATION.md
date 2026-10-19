# M32 r2 validation of G32 r2 one person, one consent (Grok self-validation, not independent review)

Candidate: G32 r2 `2d85d94fb36933357c733de80a1e988302ffc1ec` (branch review/grok-g32-consent-followthrough), direct
parent G32 r1 `589a9900203c779b55ed479e87fb88a11e406d07`, which stacks on G04 `314b4db`. Tool
`employees/sales-outreach/customer-success/followthrough.py`, doc `consent-follow-through.md`. Validator: Grok, the
same agent family that built G32. This is self-validation and does not replace an independent review. Pass window
08:29 to about 09:49 PT, Mon Oct 19 2026.

**Provenance disclosure.** The r2 fix is based on my own M32 proposed patch (`M32/proposed-fix-duplicate-handle.patch`,
published at a8f6c92). The builder generalized it (NFKC, whitespace collapse, casefold, person-keyed suppression).
So the validator here is scoring a fix it proposed. To offset that, this pass probes well beyond my own M32 probe
(rows P15, P16, O17, O18 below), and the original P05 duplicate case is only one sub-check of many.

## Verdict

PASS (self-validation) on the M32 P2-1 repair, with two P3 findings and one P4. M32 P2-1 is closed: a second
record of an opted-out person whose handle differs only by case, spacing or width is refused with nothing written.
Nothing is ever sent in any run. No P1 or P2 findings, so no proposed-fix patch this time.

## Prerequisite chain

- The patch body sha equals the diff sha (`3c501014...d226`); the patch file sha equals the handback's
  (`a5d33bf1...e941`); the manifest has 5/5 entries with 0 mismatches and its set equals the diff set. 589a990 is
  the direct parent (raw/binding-verify.txt).
- G32 r1 589a990 was validated by M32 at a8f6c92 as FAIL on P2-1; r2 is the repair. G04 314b4db was validated by M04
  at 1628e6d as PASS with residuals (P3: an owner conflict is not detected); those carry forward. The planned G04
  tightening named in both G32 handbacks has still not landed (review/grok-g04-handoff is at 314b4db), so nothing is
  superseded. If G04 moves, G32 r1 and r2 must be rebased and this redone.

## Method

- Oracle `oracle/m32r2_oracle.py`: the M32 v2 oracle unchanged (P01 to P14, with the audit hook in `oracle/audit`),
  plus r2 rows:
  - P15 person key: a second record with handle " contact-ana", "CONTACT-ANA\t", "Contact-Ana", a full-width "c",
    an all-full-width handle, a trailing NBSP, an ideographic space, and "STRAßE" vs "strasse" is refused (rc 2,
    nothing written). A missing, empty, spaces-only, tab-and-newline, number, list or null handle is refused. A
    genuinely different handle still drafts, and the clean fixture still runs.
  - P16 merge flow: with state from an earlier run, importing the duplicate is refused and the state folder is
    byte-identical; after the merge the rerun is clean and the person stays suppressed; re-importing the duplicate
    is refused again; a merge that keeps the new id while the history still names the old id fails closed (rc 2);
    a later handle change keeps the suppression (it follows the history); a merged history rewritten to the new
    id stays suppressed.
  - O17 (OBS): same state folder, the person re-imported under a new id with the old history dropped from the
    event file.
  - O18 (OBS): beyond the builder's probe: plus-addressing, a dot alias, another-domain alias, a Cyrillic "а", a
    Greek "ο", a zero-width space, a zero-width joiner, a soft hyphen, a trailing dot, and a combining accent vs a
    precomposed one, each on a second record of an opted-out person.
- Nothing is ever sent: the audit hook (positive control in M32 results/audit-positive-control.txt), the static
  import check and every draft's `send` field, as in M32 (P11).
- Controls: the real tool scores 18/18 on every interpreter; naive scores 3/18 and noop 5/18 (both include the two
  OBS rows, which always pass). Four interpreters, mutation tests on 3.13.15 and 3.9.6 with the 46 builder mutants
  copied unchanged, and a fresh caller. All of it ran on rsync copies; the candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g32: Ran 22 tests in 10.304s  OK  | full: Ran 166 tests in 22.154s  OK  | builder-oracle: ACCEPTED 11/11 | builder-naive: REJECTED 1/11 | builder-noop: REJECTED 1/11 | m32-oracle: M32R2 ORACLE 18/18 core PASS | m32-naive: M32R2 ORACLE 3/18 core FAIL | m32-noop: M32R2 ORACLE 5/18 core FAIL
== 3.11.16 | g32: Ran 22 tests in 7.968s  OK  | full: Ran 166 tests in 17.265s  OK  | builder-oracle: ACCEPTED 11/11 | builder-naive: REJECTED 1/11 | builder-noop: REJECTED 1/11 | m32-oracle: M32R2 ORACLE 18/18 core PASS | m32-naive: M32R2 ORACLE 3/18 core FAIL | m32-noop: M32R2 ORACLE 5/18 core FAIL
== 3.12.14 | g32: Ran 22 tests in 8.118s  OK  | full: Ran 166 tests in 18.515s  OK  | builder-oracle: ACCEPTED 11/11 | builder-naive: REJECTED 1/11 | builder-noop: REJECTED 1/11 | m32-oracle: M32R2 ORACLE 18/18 core PASS | m32-naive: M32R2 ORACLE 3/18 core FAIL | m32-noop: M32R2 ORACLE 5/18 core FAIL
== 3.13.15 | g32: Ran 22 tests in 8.201s  OK  | full: Ran 166 tests in 18.235s  OK  | builder-oracle: ACCEPTED 11/11 | builder-naive: REJECTED 1/11 | builder-noop: REJECTED 1/11 | m32-oracle: M32R2 ORACLE 18/18 core PASS | m32-naive: M32R2 ORACLE 3/18 core FAIL | m32-noop: M32R2 ORACLE 5/18 core FAIL
pycache in copy: 0
candidate status lines: 0
```

Mutation tests: **41/46 killed on 3.13.15 and 41/46 on 3.9.6** (results/teeth-*.log). The builder reports 46/46 with
its own tests. Survivors, each checked against the builder's tests (all are killed by them):

- teeth-3.13.15.log: redelivery_counted_twice SURVIVED
- teeth-3.13.15.log: withdrawn_redrafted SURVIVED
- teeth-3.13.15.log: torn_ledger_swallows SURVIVED
- teeth-3.13.15.log: unsubscribe_missing SURVIVED
- teeth-3.13.15.log: r2_suppression_by_record SURVIVED
- teeth-3.9.6.log: redelivery_counted_twice SURVIVED
- teeth-3.9.6.log: withdrawn_redrafted SURVIVED
- teeth-3.9.6.log: torn_ledger_swallows SURVIVED
- teeth-3.9.6.log: unsubscribe_missing SURVIVED
- teeth-3.9.6.log: r2_suppression_by_record SURVIVED
- builder tests: r2_suppression_by_record builder tests: KILL FAILED (failures=1) FAIL: test_suppression_follows_the_person (tests.test_g32_capability.G32Capability.test_suppression_follows_the_person)
- builder tests: redelivery_counted_twice builder tests: KILL FAILED (failures=2) FAIL: test_oracle_and_controls (tests.test_g32_capability.G32Capability.test_oracle_and_controls); FAIL: test_rerun_and_redelivery_never_duplicate (tests.test_g32_capability.G32Capability.test_rerun_and_redelivery_never_duplicate)
- builder tests: torn_ledger_swallows builder tests: KILL FAILED (failures=1) FAIL: test_torn_ledger_and_tampered_journal (tests.test_g32_capability.G32Capability.test_torn_ledger_and_tampered_journal)
- builder tests: unsubscribe_missing builder tests: KILL FAILED (failures=2) FAIL: test_draft_contents (tests.test_g32_capability.G32Capability.test_draft_contents); FAIL: test_oracle_and_controls (tests.test_g32_capability.G32Capability.test_oracle_and_controls)
- builder tests: withdrawn_redrafted builder tests: KILL FAILED (failures=1) FAIL: test_second_signup_and_withdrawn_never_redrafted (tests.test_g32_capability.G32Capability.test_second_signup_and_withdrawn_never_redrafted)

- r2_suppression_by_record: with duplicates refused at load, no CLI input can reach the per-person suppression,
  so it is equivalent at the CLI; the builder's unit test calls derive() directly.
- redelivery_counted_twice, torn_ledger_swallows, withdrawn_redrafted and unsubscribe_missing survive for the same
  reasons as in M32 (counters not checked; the builder's lost-log-line path; draft wording not in the doc).

Fresh caller (results/fresh-caller.txt, README demo with `STATE=$(mktemp -d)` as its heading asks): on 3.9.6 and
3.13.15 the three runs print the expected summaries, `status ... 7 open draft(s), 2 withdrawn; sent 0`, the builder
oracle ACCEPTED 11/11 and the controls REJECTED 1/11. The script exits 1 only because its last line is the noop
control. No __pycache__ and the tree is unchanged.

## Findings

- **P3-1: invisible characters defeat one person, one consent.** O18: a second record of the opted-out person with
  "ana\u200b(at)clinic.example" (zero-width space), "an\u200da(at)..." (zero-width joiner) or "ana\u00ad(at)..." (soft hyphen)
  (written here with "(at)" for the at sign) is accepted (rc 0) and gets live `welcome` and `checkin` drafts. These render the same as the original handle to a
  reviewer, NFKC does not remove them and `str.split()` does not treat them as space. The doc promises that "case,
  spacing and character width are ignored"; a zero-width space is a reasonable reading of spacing. Suggested fix:
  strip Unicode format characters (category Cf) in person_key, or refuse handles that contain them.
- **P3-2: "suppression is permanent" holds only while the event file keeps the opt-out.** O17: after a run where
  c-ana opted out, the same state folder is run with the person re-imported as c-ana2 (same handle) and an event
  file that no longer carries c-ana's history. The tool drafts a `welcome` to her (rc 0). The state remembers drafts
  by key, not suppressions by person, so a merge that drops the old record's history (common in CRM merges) loses
  the opt-out. The doc should say the event file must keep every opt-out for the person, or the state should keep a
  per-person suppression list.
- **P4-1: the doc does not name what it does not match.** O18: plus-addressing, dot and domain aliases, Cyrillic or
  Greek look-alikes and a trailing dot are each a different person to the tool, and the opted-out person gets live
  drafts. The handback says this is by design (handles are opaque; the sending system maps them), and a combining
  accent vs a precomposed one is correctly merged by NFKC. But the doc only says what is matched; it should say
  that aliases and look-alikes are not, so whoever imports contacts resolves them first.
- OBS (unchanged from M32): no consent expiry; suppression is permanent until a person reviews it.

## Disclosures

- The fix being scored came from my own M32 patch (above).
- Oracle authoring fix after the first run (kept as results/kept/oracle-authoring-run-3.9.6.json, 18/18): the
  "different people still fine" check used `contact-ben`, which is c-ben's handle, and accepted rc 2; it now uses
  `contact-zed` and requires drafts.
- Publish-safety edit after the matrix and mutation runs: the safety scan flagged the address-shaped synthetic
  handles in O18, so the source now writes them with "(at)" and substitutes the real character at run time. I did not
  loosen the scanner. I reran the oracle on 3.9.6 and 3.13.15 after the edit: 18/18 both times, and O18's detail is
  identical to the matrix run.
- Harness: the M32 v2 harness (a kill is a change in a row's pass value or any named sub-check) and the M32 fresh
  caller with `STATE=$(mktemp -d)`, both already disclosed in M32.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there and its branch, index and status are unchanged.
