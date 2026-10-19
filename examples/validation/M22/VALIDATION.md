# M22 validation of G22 signed-webhook order ledger (Grok self-validation, not independent review)

Candidate: G22 `1faee8d4e529fbbeac7c64292bed324bdced9796` (branch review/grok-g22-payment-ledger), parent merge
`c9109b7` of G14 r2 (6f7b23a) and G19 (5606672). Tool `employees/specialized/payments-specialist/payment_ledger.py`,
doc `webhook-ledger.md`. Validator: Grok, the same agent family that built G22. This is self-validation and does not
replace an independent review. Pass window 05:54 to about 06:44 PT, Mon Oct 19 2026.

## Verdict

PASS (self-validation). No P1, P2 or P3 findings. There is one P4 finding (an inherited flaky test) and OBS notes.

## Prerequisite chain

- The patch sha equals the diff sha (`5143b95d...7d40`); the manifest has 18/18 entries with 0 mismatches and its set
  equals the diff set. Merge c9109b7 has parents 6f7b23a and 5606672, and its tree da3c0fc equals `git merge-tree` of
  the two (raw/binding-verify.txt).
- G14 r2 was validated by M14 r2 at 60682d2. G19 was validated by M19 at f2e52da as PASS **with adversarial findings**
  (in M19 the candidate rejected the attack in only 6/19 or 7/19 adversarial cross-checks). Those findings carry
  forward; M22 did not re-test G19.
- Nothing in the chain is superseded as far as the branch listing shows.

## Method

- Fresh oracle `oracle/m22_oracle.py`, written from M22.md, G22.md and webhook-ledger.md before I read the builder's
  oracle. It signs its own envelopes (HMAC-SHA256 over `<t>.<body>` with its own local test value), keeps its own
  integer-cents money and stock model, and drives the CLI in fresh temp dirs.
- Core rows:
  - B01 clean stream.
  - B02 signature and time: tampered body, wrong secret, t 301 s stale or in the future, a missing t, and a signature
    reused with another t are all refused with nothing stored. The 300 s boundary is accepted. A forged event in a mixed
    batch is refused while the good one applies.
  - B03 replay: duplicates within a batch, across runs and re-signed are applied once. The same id with another body is
    `conflicting_replay`. A reused payment id is an exception.
  - B04 out of order: a reversed stream equals the in-order one. Held events are listed (exit 1) and applied when their
    order arrives, including a refund that arrives before its capture.
  - B05 oversell: 10 processes race for 4 tee-m, 5 trials. Exactly 4 are reserved and 6 are out_of_stock, there is no
    "database is locked", and check is consistent. 6 concurrent deliveries of one capture capture once.
  - B06 over-refund: refused as refund_exceeds_captured and kept as unapplied money. The exact remainder is accepted;
    1 cent over is refused.
  - B07 over-restock: refused as restock_exceeds_shipped, including a SKU that is not in the order.
  - B08 exact cents: 3 x 0.10, refunds of 0.10 sum exactly, 3 x 19.99, a JSON float amount and a float `created` are
    refused, `0.300` is not applied, and 0.29 is capture_amount_mismatch.
  - B09 crash drill at every N, then rerunning the whole batch, reaches the clean end state.
  - B10 export-g14 then G14 `reconcile --json`: every check is ok, the exceptions are empty, and recognized revenue and
    net cash equal the ledger's net cash. This holds for the september fixture (32.69) and two of my own streams (32.49).
  - B11 cancel releases the reservation; capture after cancel and cancel after capture are named anomalies.
  - B12 seeded soak: shuffled captures and refunds, duplicates and a crash restart on an ample catalog equal an
    independent cents model.
  - B13 a reused refund id is an exception.
  - B14 an exception writes no partial restock.
  - B15 check names each broken invariant on its own and is read-only.
  - B16 race: 24 mixed processes (ingest, report, check) on one fresh ledger, 3 trials, with no "database is locked"
    and stock conserved.
- Controls: the real tool scores 16/16, naive_ledger 10/16 and noop_ledger 0/16.
- Four interpreters, mutation tests on 3.13.15 and 3.9.6 with the 34 builder mutants copied unchanged, and a fresh
  caller (README demo verbatim under `env -i` with a new HOME). All of it ran on rsync copies; the candidate was never
  modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g22: Ran 12 tests in 11.198s  OK  | full: Ran 162 tests in 114.189s  OK  | builder-oracle: PASSED 10/10 | builder-naive: REJECTED 5/10 | builder-noop: REJECTED 0/10 | m22-oracle: M22 ORACLE 16/16 core PASS | m22-naive: M22 ORACLE 10/16 core FAIL | m22-noop: M22 ORACLE 0/16 core FAIL
== 3.11.16 | g22: Ran 12 tests in 7.794s  OK  | full: Ran 162 tests in 104.190s  OK  | builder-oracle: PASSED 10/10 | builder-naive: REJECTED 5/10 | builder-noop: REJECTED 0/10 | m22-oracle: M22 ORACLE 16/16 core PASS | m22-naive: M22 ORACLE 10/16 core FAIL | m22-noop: M22 ORACLE 0/16 core FAIL
== 3.12.14 | g22: Ran 12 tests in 5.533s  OK  | full: Ran 162 tests in 101.403s  OK  | builder-oracle: PASSED 10/10 | builder-naive: REJECTED 5/10 | builder-noop: REJECTED 0/10 | m22-oracle: M22 ORACLE 16/16 core PASS | m22-naive: M22 ORACLE 10/16 core FAIL | m22-noop: M22 ORACLE 0/16 core FAIL
== 3.13.15 | g22: Ran 12 tests in 5.221s  OK  | full: Ran 162 tests in 101.352s  OK  | builder-oracle: PASSED 10/10 | builder-naive: REJECTED 5/10 | builder-noop: REJECTED 0/10 | m22-oracle: M22 ORACLE 16/16 core PASS | m22-naive: M22 ORACLE 10/16 core FAIL | m22-noop: M22 ORACLE 0/16 core FAIL
pycache in copy: 0
candidate status lines: 0
```

Mutation tests: **32/34 killed on 3.13.15 and 32/34 on 3.9.6**. The builder's oracle alone kills 23/34 (handback).
The survivors on both versions are exactly the two the builder claimed equivalent:

- `exception_partial_writes_kept` (3.13.15: survived; 3.9.6: survived). exception_partial_writes_kept builder tests: no kill OK 
- `wal_every_open` (3.13.15: survived; 3.9.6: survived). wal_every_open builder tests: no kill OK

- exception_partial_writes_kept: B14 tried a refund whose first restock line is valid and whose second exceeds what
  shipped. Nothing was written, because the tool checks before it writes, so the savepoint rollback is not reached.
  I agree it is equivalent for every input I could construct.
- wal_every_open: init already puts the ledger in WAL, so a per-open `journal_mode=WAL` is a no-op. B05 and B16
  (concurrent ingests plus readers, 8 trials) saw no "database is locked". I agree it is equivalent on ledgers made by
  init. The builder's real defect (raw/found-defect-wal-race.txt in G22) was WAL set on open while init did not set it;
  that variant is not among the mutants.

Fresh caller (results/fresh-caller.txt): on 3.9.6 and 3.13.15 both ingests exit 3 and the replay changes nothing. The
report reads `USD net cash 32.69 (captured 45.29, refunded 12.60); 2 held or exception events`, check is `consistent`,
and G14 prints `reconciled` with revenue 32.69 and net cash 32.69, matching the README's hand-worked figures. No pycache
was written and the tree was unchanged. On 3.9.6, HOME gained `Library/Caches/com.apple.python`, which comes from Apple's
interpreter.

## Findings

P4-1 (inherited flaky test): the full suite failed once in 5 runs on 3.9.6 (1 failure in the v1 matrix and 1 of 3
repeat runs in results/flake, both under heavy machine load). The failing test is
`test_g19_capability.ProbeAndOracle.test_oracle_accepts_real_api_and_rejects_stubs`: the G19 oracle's o8 (server crash
and restart) saw `PermissionError: [Errno 1] Operation not permitted`. This is G19 code inherited through the merge,
not G22. The G22 goal module passed every time. It is likely a process-signal race under load; I did not root-cause it.

OBS-1 (documented): held events wait forever, with no expiry or alert (doc Limits).

OBS-2: an amount with three decimals (`"0.300"`) becomes an open `exception` (exit 1), not a refused envelope (exit 3).
It is not applied and is visible, but it stays open, and there is no resolve command, so every later ingest exits 1.
The doc says only "is not an amount", so this is consistent with the doc. A JSON float, by contrast, is refused (exit 3).

OBS-3: a capture must equal the order total (one capture per order), as documented. Handback open questions 1 to 4 are
design choices the doc states.

OBS-4: the prerequisite G19 carries M19's adversarial findings (above).

## Disclosures

- Oracle authoring fixes before I scored against the controls (the first run is kept in results/kept, 9/12):
  - B07: exit 1 means some exception is open anywhere in the ledger, not only in this batch.
  - B08: `"0.300"` may be refused or kept as an exception, as long as it is not applied.
  - B10: G14 has no top-level status, so I read every checks.*.ok and the exceptions lists instead.
- Oracle v1 to v2 to v3:
  - v1 killed 27/34 (results/v1). v2 added B13 to B16 and killed 29/34 (results/v2, 3.13.15).
  - v3 made B15 also require that the check output names the tampered invariant. The doc says check "names each
    broken invariant", but the tampers and keywords were chosen after I looked at the candidate's check output on a
    tampered copy (grey box).
  - Final numbers are from v3, rerun from scratch.
- The teeth harness is the M09 template, with its score function adapted to this oracle's JSON format.
- No fix patch was produced, because there is no P1 or P2.
