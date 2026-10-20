# M22 h2: recheck of G22 h2 29cd7fc (Grok self-validation, not independent review)

Verdict: **PASS, M22 h1 P3-1 closed, no new P1 to P3.** G22 h2 adds `payment_ledger.py resolve` (retry or close, with
who, why and a reference). After the september exceptions are closed, September and November export again and G14
reconciles at 32.69. Closed money is shown as closed, never as cash. Refusals and tampering behave. This is Grok checking
a Grok build, so it is not independent review and accepts nothing.

## Binding (raw/binding-verify.txt)
- Candidate 29cd7fc6a07384db28fca3824b7fc4efe1d13fe3, the current remote head of review/grok-g22-payment-ledger. It is
  a 2-commit fast-forward from G22 h1 8bc3553: ac2b2d0 is the change and 29cd7fc is test-only.
- The handback G22-h2.patch equals `git diff --binary 8bc3553 29cd7fc`. MANIFEST matches, and the manifest set
  equals the diff set.

## New probe for this pass (oracle/m22h2_probe.py, results/probe-*)
The cases are mine. They use the shipped september fixture plus events the probe signs itself with the fixture test
secret.
- **R1:** close evt_008 (note only, no money) and evt_007 (40.00 over-refund, `--reference`).
  - November export exits 0. September export exits 0 and G14 reconciles at 32.69.
  - The report shows closed_unapplied_refunds 40.00 and net cash 32.69, plus 2 audit rows with who, why, prior
    reason and reference.
  - Export stdout lists the closed 40.00 under closed_money_not_in_books. check exits 0.
- **R2:** resolving evt_007 a second time (close, then retry) exits 2 both times. There are still 2 audit rows.
- **R8:** re-delivering the closed evt_007 is a duplicate (ingest exits 0). It stays resolved and export still exits 0.
- **R6:** tampering with the sqlite file after resolve is reported by check (exit 1, named). The cases:
  - deleted record
  - changed closed amount
  - dropped reference
  - applied event marked resolved
  - resolved event set back to exception
- **R3:** each of these refusals exits 2, and nothing is recorded. Export stays refused (exit 1).
  - money close with no reference
  - blank reference
  - applied event
  - unknown id
  - blank --by or --note
  - both --reference and --superseded-by
- **R4:** `--superseded-by` is refused (exit 2) for another order's applied refund, a held event, an unknown id, or
  the event itself. A signed re-delivered refund on the same order (applied) is accepted and recorded.
- **R5:** a probe-signed out-of-stock order evt_303 with its held capture evt_304.
  - Retry while still out of stock exits 1, nothing changes and no record is written.
  - After a restocking return arrives, retry applies evt_303 and the held capture follows.
  - Export exits 0, G14 reconciles, and the audit row says retry.
- **R7:** a held refund. Retry before its order arrives exits 1 and it stays held. Once ingest applies it, resolve
  refuses (exit 2).
- **R9:** a ledger made by the h1 tool (8bc3553 payment_ledger.py, no resolutions table) can be resolved by h2. The
  table is created, export exits 0 and check exits 0.
- **Results:** 9/9 on h2 and 1/9 on h1 8bc3553, on Python 3.9.6, 3.11.16, 3.12.14 and 3.13.15. On h1 only R3
  "passes", and only because argparse rejects the unknown `resolve` command with exit 2.

## Earlier probes and oracles, unchanged (oracle/m22h1_probe.py, oracle/m22_oracle.py)
- **M22 h1 probe:** 6/6 on h2, all four Pythons.
  - Q5 still records that re-delivering evt_007 alone does not clear it, and a later November export stays refused
    until it is resolved. That is the design: re-delivery under the same id is a duplicate, and clearing is the
    explicit `resolve` (now listed in the commands).
- **M22 oracle:** 15/16 core on h2, all four Pythons. The one failure is the same B10 as on h1: its streams carry an
  open 40.00 over-refund and export now refuses them. This was expected and reasoned in M22 h1.

## Builder checks (results/builder-checks.txt, results/full-suite-matrix.txt)
- ledger_oracle PASSED 10/10, naive REJECTED 5/10, no-op REJECTED 0/10.
- tests.test_g22_capability: 20 OK on each of the four Pythons.
- Full suite on fresh clones at 29cd7fc: 170 OK on all four Pythons. Browser processes 0.

## Notes (not findings against the build)
- **OBS-1:** `--by` is recorded, not authenticated, and the doc says so. Anyone who can write the ledger file can
  resolve.
- **OBS-2:** closing an out-of-stock order does not close a capture held for that order. The capture stays held and
  blocks export until it is resolved on its own (a reference is required, since it carries money). This is explicit,
  not silent.
- **Disclosure:** G22 h2's first commit ac2b2d0 carried the owner's name as a sample operator in two test lines. It was
  pushed despite 3 safety-scan hits and fixed by the test-only 29cd7fc. See the G22 h2 handback.

Browser launches for this pass: 0.
