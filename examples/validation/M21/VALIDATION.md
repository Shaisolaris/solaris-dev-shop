# M21 validation of G21 offline outbox (Grok self-validation, not independent review)

Candidate: G21 `822a9c1aaf2da3a0dace1bd0a0640d992406efa0` (branch review/grok-g21-offline-sync), parent G19
`5606672b464f5daaf08e28cbfa5a8d307f730c27`. Tool `employees/engineering/mobile-developer/offline_sync.py`, doc
`offline-sync.md`. Validator: Grok, the same agent family that built G21. This is self-validation and does not replace
an independent review. Pass window 05:54 to about 06:44 PT, Mon Oct 19 2026.

## Verdict

PASS (self-validation). No P1, P2 or P3 findings. The tool held every rule in the doc under faults chosen by my own
proxy, not by the tool. Observations only (OBS) are below.

## Prerequisite chain

- The patch sha equals the diff sha (`08d7b661...a00c`); the manifest has 14/14 entries with 0 mismatches and its set
  equals the diff set. The parent 5606672 is an ancestor. Details are in raw/binding-verify.txt.
- G19 5606672 was validated by M19 at f2e52da as PASS **with adversarial findings**: in M19 the candidate rejected
  the attack in only 6/19 or 7/19 adversarial cross-checks (findings, not a verdict change). G21 builds on that API, so
  those M19 findings carry forward. M21 did not re-test G19 itself.
- Nothing in the chain is superseded as far as the branch listing shows: main is 02ba9c5, and the G19, G21 and G22
  review branches are at the bound SHAs.

## Method

- Fresh oracle `oracle/m21_oracle.py`, written from M21.md and offline-sync.md before I read the builder's oracle. It
  runs the real G19 ledger server on loopback with my own fault proxy in front of it (503, a connection dropped before
  forwarding, a lost ack where the server commits and the answer is dropped, slow, and synthetic 404 and 422). It
  judges from the server side (the invoices the ledger holds, `ledger_api.py check`) against an intent model kept in
  the oracle.
- Core rows: A01 clean batch; A02 lost ack on each request in turn; A03 503 and drop; A04 client crash before and after
  each send; A05 order of intent; A06/A06b overpay conflict held, then discard and the held change is sent; A07 void
  versus pay with a retry under a new key; A08 a stale snapshot never rolls back; A09 four concurrent syncs, one runs
  and three exit 5; A10 refused keys exit 3; A11 invalid input exits 2; A12 key format and a unique install; A13 check
  catches a tampered outbox; A14 seeded soak with 3 devices and random faults; A15 422 rejected, 404 conflict, a change
  waits for its create, resolve works only on problems, discard cascades; A16 drop or unreachable server leaves no
  answer on a pending change, non-loopback exits 2, init refuses an existing outbox; A17 each check invariant on its own;
  A18 projected balance counts pending changes; A19 apply-snapshot counts.
- Controls: the real tool scores 20/20, naive_sync 9/20 and noop_sync 0/20. (My oracle's summary line prints the word
  "PASS" after the count even when rows fail. That is a cosmetic label bug in my oracle; the counts are right.)
- All four interpreters (3.9.6, 3.11.16, 3.12.14, 3.13.15): the matrix is below.
- Mutation tests: 31 builder mutants copied unchanged from G21/scripts/mutants.py, run on 3.13.15 and 3.9.6.
- Fresh caller: the README demo, verbatim, under `env -i` with a new HOME on 3.9.6 and 3.13.15.
- Everything ran on rsync copies. The candidate worktree was never modified (0 status lines). week-grok before and
  after records are in raw/.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g21: Ran 12 tests in 69.399s  OK  | full: Ran 112 tests in 157.063s  OK  | builder-oracle: PASSED 13/13 | builder-naive: REJECTED 4/13 | builder-noop: REJECTED 0/13 | m21-oracle: M21 ORACLE 20/20 core PASS | m21-naive: M21 ORACLE 9/20 core PASS | m21-noop: M21 ORACLE 0/20 core PASS
== 3.11.16 | g21: Ran 12 tests in 50.404s  OK  | full: Ran 112 tests in 150.198s  OK  | builder-oracle: PASSED 13/13 | builder-naive: REJECTED 4/13 | builder-noop: REJECTED 0/13 | m21-oracle: M21 ORACLE 20/20 core PASS | m21-naive: M21 ORACLE 9/20 core PASS | m21-noop: M21 ORACLE 0/20 core PASS
== 3.12.14 | g21: Ran 12 tests in 68.710s  OK  | full: Ran 112 tests in 160.057s  OK  | builder-oracle: PASSED 13/13 | builder-naive: REJECTED 4/13 | builder-noop: REJECTED 0/13 | m21-oracle: M21 ORACLE 20/20 core PASS | m21-naive: M21 ORACLE 9/20 core PASS | m21-noop: M21 ORACLE 0/20 core PASS
== 3.13.15 | g21: Ran 12 tests in 51.784s  OK  | full: Ran 112 tests in 132.677s  OK  | builder-oracle: PASSED 13/13 | builder-naive: REJECTED 4/13 | builder-noop: REJECTED 0/13 | m21-oracle: M21 ORACLE 20/20 core PASS | m21-naive: M21 ORACLE 9/20 core PASS | m21-noop: M21 ORACLE 0/20 core PASS
pycache in copy: 0
candidate status lines: 0
```

Mutation tests (results/teeth-3.13.15, results/teeth-3.9.6): **29/31 killed on 3.13.15 and 29/31 on 3.9.6**.
The builder's oracle alone kills 21/31 (handback). The survivors on both versions:

- `no_wait_for_create` (3.13.15: survived; 3.9.6: survived). no_wait_for_create builder tests: KILL FAILED (failures=1) FAIL: test_pull_is_tenant_scoped_and_discarding_a_create_names_its_dependents (tests.test_g21_capability.G21Capability)
- `network_error_swallowed` (3.13.15: survived; 3.9.6: survived). network_error_swallowed builder tests: KILL FAILED (failures=1) FAIL: test_server_crash_after_commit_and_transient_failure_keep_one_effect_and_order (tests.test_g21_capability.G21Capability)

The builder's goal tests kill both (results/survivors-builder-tests.txt), so they are blind spots in my oracle, not
equivalent mutants. no_wait_for_create survives because, in every scenario I built, the unmapped create also blocks
the change by another path. network_error_swallowed survives because a swallowed network error comes back as a 599,
which the tool then treats as transient (exit 4, still pending, no stored answer), so my black-box rows see the same
result.

Fresh caller (results/fresh-caller.txt): on both versions the demo exits 0, the crash drill exits 70, and the second
run sends 2 (the replayed payment plus the last one). It ends at `0 pending, 3 acked`, and both checks print
`consistent`. No pycache was written and the tree was unchanged. On 3.9.6, HOME gained `Library/Caches/com.apple.python`,
which comes from Apple's interpreter, not from the tool.

## Findings

None at P1 to P4.

OBS-1 (documented limit): a change behind a conflict is held even when it would fit on its own. In O15 a pay of 200
conflicts (exceeds_balance) and a later pay of 100 on the same invoice stays `pending` with waiting "held behind op 1
(conflict) on the same invoice" until the user resolves op 1. This is rule 3 as written.

OBS-2 (documented limit): a retried change goes to the back of the outbox, so it can land after later changes to the
same invoice (handback open question 1; the doc's Limits section says so).

OBS-3: the prerequisite G19 carries M19's adversarial findings (above).

## Disclosures

- Oracle authoring fixes, made before I scored against the controls (the first run is kept in results/kept): A05 and
  A06b voided an invoice that already had a payment, which G19 refuses (409 cannot_void), so my expected end state was
  wrong. A13 looked for an `idempotency_key` column while the outbox column is `idem`.
- Oracle v1 to v2: the v1 teeth run killed only 18/31 on 3.13.15 (kept in results/v1). Its survivors showed doc rules
  v1 never exercised, so v2 added A15 to A19, each tied to a doc sentence. v1 rows are unchanged. All final numbers are
  from v2, rerun from scratch.
- The proxy's synthetic 404/422 answers are my fault injection, not server behaviour.
- The teeth harness is the M09 template with names changed. No fix patch was produced, because there is no P1 or P2.
