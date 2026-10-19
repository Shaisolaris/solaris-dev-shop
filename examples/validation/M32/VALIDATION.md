# M32 validation of G32 consent-aware follow-through (Grok self-validation, not independent review)

Candidate: G32 `589a9900203c779b55ed479e87fb88a11e406d07` (branch review/grok-g32-consent-followthrough), direct
parent G04 `314b4dbf980437cf14bc32438117e5b5b777f942`. Tool `employees/sales-outreach/customer-success/followthrough.py`,
doc `consent-follow-through.md`. Validator: Grok, the same agent family that built G32. This is self-validation and
does not replace an independent review. Pass window 06:53 to about 08:08 PT, Mon Oct 19 2026.

## Verdict

FAIL (self-validation) on one P2 finding: a duplicate import of an opted-out person under a second contact id gets
live follow-up drafts. Nothing is ever sent in any run (proved three ways below). A proposed fix is included,
positive-controlled on a private copy and **not applied**; it is my own patch, not the builder's.

## Prerequisite chain

- The patch sha equals the diff sha (`cc2939e9...5fdc`); the manifest has 18/18 entries with 0 mismatches and its set
  equals the diff set. 314b4db is the direct parent (raw/binding-verify.txt).
- G04 314b4db was validated by M04 at 1628e6d as PASS **with residuals** (P3: an owner conflict is not detected; plus
  a P4). G32 loads G04's Journal, try_lock and atomic_write, so those residuals carry forward; M32 did not re-test G04.
- The G32 handback names a "planned G04 tightening" with a rebase rule. As of this pass it has not landed:
  review/grok-g04-handoff is still at 314b4db, so nothing in the chain is superseded. If G04 moves, G32 must be rebased
  and this validation redone.

## Method

- Fresh oracle `oracle/m32_oracle.py` (v2), written from M32.md, G32.md and the doc before I read the builder's
  oracle. It drives the real CLI in fresh temp dirs on edited copies of the fixture.
- **Nothing is ever sent**, checked three ways on every run of the oracle:
  1. An audit hook (`oracle/audit/sitecustomize.py`, loaded through PYTHONPATH into every tool process) logs any
     socket connect, getaddrinfo or bind, subprocess, os.system, exec, spawn or fork, smtplib, urllib request,
     http.client or webbrowser use. Positive control (results/audit-positive-control.txt): a script that connects a
     socket and starts a process produces 2 log lines. Across all oracle runs the log stayed empty (P11).
  2. A static check that the tool imports none of socket, smtplib, urllib, http.client, subprocess, requests, ftplib
     or webbrowser (P11).
  3. Every draft's `send` field is "not performed; a person reviews and sends" or "do not send", and status always
     reports `sent 0`.
- Consent probes, by the four kinds in the request:
  - **Withdrawn** (P02): an opt-out with scope all and a hard bounce withdraw open drafts with "do not send" and never
    redraft them; a soft bounce does not suppress.
  - **Expired** (P03): consent values expired, withdrawn, revoked, empty, null and GRANTED are refused (rc 2, nothing
    written). A past `consent_expires` field is ignored; the doc has no expiry concept (OBS-1).
  - **Partial** (P04): a marketing-only opt-out and unknown consent keep support replies (ack, nudge) and drop
    onboarding and feedback.
  - **Conflicting** (P05): opt-out then opt-in, opt-in then opt-out, a same-instant tie and marketing then all are all
    suppressed, and an opt-in after an opt-out raises `consent_review_required`; a duplicate contact id is refused, an
    exact redelivery counts once, and the same event id with other content is refused. **The duplicate import of one
    person (same handle, second contact id) is not caught (P2-1).**
- Other rows: P01 clean fixture (7 hand-derived drafts, current owner, no send); P06 a reopened ticket gets its own
  ack and nudge; P07 rerun idempotence, a crash at drafted or at ledgered (75 then 0, 7 drafts) and 5 racing workers
  (one runs, the rest exit 4); P08 owner reassignment; P09 a tampered journal or another account's state is refused,
  a removed draft is noted and not redrafted, a torn ledger line; P10 a seeded soak of 8 random histories; v2 rows
  P12 exact-minute timing for every action (+0, +3 d, +7 d, +2 d, +1 d), second signup, reply and close cancellation
  and a future opt-out, P13 invalid input (ticket without thread, opt-out without or with an unknown scope, unknown
  contact, a time without offset, a bad worker name) refused with nothing written, P14 every draft after a torn
  ledger line has a parseable ledger record.
- Controls: the real tool scores 13/14 (only P05 fails); naive_followthrough scores 1/14 and noop_followthrough 3/14
  on every interpreter (matrix). Four interpreters, mutation tests on 3.13.15 and 3.9.6 with the 36 builder mutants copied unchanged, and a
  fresh caller. All of it ran on rsync copies; the candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g32: Ran 20 tests in 10.139s  OK  | full: Ran 164 tests in 24.467s  OK  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 1/10 | builder-noop: REJECTED 1/10 | m32-oracle: M32 ORACLE 13/14 core FAIL | m32-naive: M32 ORACLE 1/14 core FAIL | m32-noop: M32 ORACLE 3/14 core FAIL
== 3.11.16 | g32: Ran 20 tests in 8.416s  OK  | full: Ran 164 tests in 19.208s  OK  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 1/10 | builder-noop: REJECTED 1/10 | m32-oracle: M32 ORACLE 13/14 core FAIL | m32-naive: M32 ORACLE 1/14 core FAIL | m32-noop: M32 ORACLE 3/14 core FAIL
== 3.12.14 | g32: Ran 20 tests in 8.894s  OK  | full: Ran 164 tests in 19.410s  OK  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 1/10 | builder-noop: REJECTED 1/10 | m32-oracle: M32 ORACLE 13/14 core FAIL | m32-naive: M32 ORACLE 1/14 core FAIL | m32-noop: M32 ORACLE 3/14 core FAIL
== 3.13.15 | g32: Ran 20 tests in 9.220s  OK  | full: Ran 164 tests in 19.172s  OK  | builder-oracle: ACCEPTED 10/10 | builder-naive: REJECTED 1/10 | builder-noop: REJECTED 1/10 | m32-oracle: M32 ORACLE 13/14 core FAIL | m32-naive: M32 ORACLE 1/14 core FAIL | m32-noop: M32 ORACLE 3/14 core FAIL
pycache in copy: 0
candidate status lines: 0
```

Mutation tests: **v2 oracle 32/36 killed on 3.13.15 and 31/36 on 3.9.6** (results/teeth-*.log). The v1 oracle and
harness killed 21/36 on both (results/v1). The builder reports 36/36 with its own tests. Survivors, each checked
against the builder's tests (all are killed by them):

- teeth-3.13.15.log: redelivery_counted_twice SURVIVED
- teeth-3.13.15.log: withdrawn_redrafted SURVIVED
- teeth-3.13.15.log: torn_ledger_swallows SURVIVED
- teeth-3.13.15.log: unsubscribe_missing SURVIVED
- teeth-3.9.6.log: redelivery_counted_twice SURVIVED
- teeth-3.9.6.log: withdrawn_redrafted SURVIVED
- teeth-3.9.6.log: no_lock SURVIVED
- teeth-3.9.6.log: torn_ledger_swallows SURVIVED
- teeth-3.9.6.log: unsubscribe_missing SURVIVED
- builder tests: no_lock builder tests: KILL FAILED (failures=2) FAIL: test_lock_held_writes_nothing (tests.test_g32_capability.G32Capability.test_lock_held_writes_nothing); FAIL: test_oracle_and_controls (tests.test_g32_capability.G32Capability.test_oracle_and_controls)
- builder tests: redelivery_counted_twice builder tests: KILL FAILED (failures=2) FAIL: test_oracle_and_controls (tests.test_g32_capability.G32Capability.test_oracle_and_controls); FAIL: test_rerun_and_redelivery_never_duplicate (tests.test_g32_capability.G32Capability.test_rerun_and_redelivery_never_duplicate)
- builder tests: torn_ledger_swallows builder tests: KILL FAILED (failures=1) FAIL: test_torn_ledger_and_tampered_journal (tests.test_g32_capability.G32Capability.test_torn_ledger_and_tampered_journal)
- builder tests: unsubscribe_missing builder tests: KILL FAILED (failures=2) FAIL: test_draft_contents (tests.test_g32_capability.G32Capability.test_draft_contents); FAIL: test_oracle_and_controls (tests.test_g32_capability.G32Capability.test_oracle_and_controls)
- builder tests: withdrawn_redrafted builder tests: KILL FAILED (failures=1) FAIL: test_second_signup_and_withdrawn_never_redrafted (tests.test_g32_capability.G32Capability.test_second_signup_and_withdrawn_never_redrafted)

- no_lock survived on 3.9.6 only: the 5-worker race in P07 is timing-dependent, so it does not always overlap.
- redelivery_counted_twice: my oracle checks that redelivery never makes a second draft, not the summary counters.
- torn_ledger_swallows and withdrawn_redrafted: my torn-ledger and withdraw probes did not reach the exact path (the
  builder's test loses the opt-out line from the log); the builder's tests kill both.
- unsubscribe_missing: the doc does not mention an unsubscribe line, so my oracle, written from the doc, does not
  check draft wording.

Fresh caller (results/fresh-caller.txt): on 3.9.6 and 3.13.15 the three demo runs print the expected summaries, the
consent_review_required note for c-dee, `status ... sent 0`, the builder oracle ACCEPTED 10/10 and the naive and noop
controls REJECTED 1/10. The script exits 1 only because its last line runs the noop control. No __pycache__ and the
tree is unchanged.

## Findings

- **P2-1: a duplicate import of an opted-out person gets live drafts.** P05 adds contact `c-ana2` with the same
  handle `contact-ana` as `c-ana`, who opted out (scope all), and a signup for c-ana2. The run exits 0 and writes
  `welcome` and `checkin` drafts with status `draft` addressed to the opted-out handle. Consent belongs to the person,
  not the record, so this defeats the opt-out. Nothing is sent (a person still reviews), but a reviewer is handed a
  ready draft to someone who withdrew. Proposed fix (`proposed-fix-duplicate-handle.patch`, my own, not applied):
  `load_account` requires a non-empty handle and refuses a second contact with the same handle ("merge the duplicate
  import first", rc 2). Positive control on a private copy (results/fix-positive-control.txt with the v1 oracle,
  results/fix-positive-control-v2.txt with v2): P05 passes, M32 ORACLE 14/14, tests.test_g32_capability 20 OK and the
  builder oracle ACCEPTED 10/10.
- OBS-1: there is no consent expiry. A `consent_expires` in the past is ignored and drafts are made. The doc does not
  promise expiry, so this is not scored, but "expired consent" in the request has no direct mechanism; an expired
  consent can only be expressed by changing `consent` to unknown.
- OBS-2: suppression is permanent until a person reviews (`consent_review_required`); a later opt-in never
  re-enables drafts automatically. That is the fail-closed reading and matches the doc.

## Disclosures

- The proposed fix is my own patch. Scoring it positive does not mean the builder fixed anything.
- Oracle and harness changes, all after first runs (kept in results/kept):
  - v1 first run (results/kept/oracle-first-run-3.9.6.json) was kept before any change.
  - v2 added P12, P13 and P14 after the v1 mutation run left 15 survivors. One v2 authoring fix: P12's first step
    expected an ack at 09:00 for a ticket that opens at 10:00 (my error); the first v2 run is kept as
    results/kept/oracle-v2-authoring-run-3.9.6.json.
  - v2 harness: a mutant now counts as killed when a row's pass value **or any of its named sub-checks** changes.
    Under v1 the real P05 failure masked every other P05 sub-check, so mutants there could not be killed.
  - Fresh caller: the README demo uses `$STATE`, "an empty temporary folder" per its heading, which is unset under
    `env -i`. The harness now prepends `STATE=$(mktemp -d)`; the first run with the usage errors is kept as
    results/kept/fresh-caller-without-STATE.txt.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there and its branch, index and status are unchanged.
