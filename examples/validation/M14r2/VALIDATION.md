# M14 r2: Grok self-validation of G14 r2 (cash vs revenue, over-refund and over-credit exceptions)

This is Grok self-validation, not independent review. The same agent family built and validated it.

- Candidate: G14 r2 `6f7b23aa18413907c5fbd250daab475dc94e7a1e` on `review/grok-g14-cash-revenue`, a fast-forward
  from r1 `76b9c669359214c5dbe06768c78229beb54a4eae` (scored by M14 `a07d54e`: PASS with P3-1 and P4-1).
- Prerequisites unchanged: G13 r3 `5666e7b` (contained), main `02ba9c5`. Nothing superseded. Patch sha256 equals
  `git diff --binary 76b9c66 6f7b23a`; manifest 7/7, 0 mismatches (`raw/binding-verify.txt`).
- The candidate was never modified; every run used an rsync copy (or a `git archive` of r1 for the base control) in a
  private temp dir. week-grok before/after records are identical. Pass window 03:20 to about 03:40 PT, 2026-10-19.
- The fix is the builder's design, not from a Grok patch (M14 r1 had no P1/P2 and supplied no patch).

## Verdict: PASS. P3-1 and P4-1 (M14 r1) are fixed; no new finding above OBS.

| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| G14 tests / full suite | 10 OK / 134 OK | same | same | same |
| builder oracle (seed 1409) real / naive / noop | 13/13 / 1/13 / 0/13 | same | same | same |
| M14 oracle v3 (regression) real / naive / noop | 19/19 / 1/18 / 1/19 | same | same | same |
| new negative-transaction oracle `m14r2_negative.py` v2 real / naive | 16/16 / 4/16 | same | same | same |

- Base control: the r2 oracle on r1 `76b9c66` scores 7/15 (v1 rows). Every over-refund and over-credit row fails
  there (exit 0, no exception), and equal amounts, separate checks and exclusions pass, as they should.
- Regression: the only M14 v3 row that changed is the OBS row K14 (rc 0 with no exceptions, now rc 1 with both
  exceptions named and the same closing balances), which is the intended P3-1 fix. The naive control's 1/18 is the
  same as r1 (one row does not run on the stub).
- Fresh caller (env -i, new HOME, README commands only) on 3.9.6 and 3.13.15: identical, README exit codes and per-
  currency figures, no stray files or bytecode.
- Teeth (39 builder mutants, unchanged, scored by `m14r2_all.py` = M14 oracle v3 + r2 oracle v2): 3.13.15 38/39,
  3.9.6 37/39. All 8 r2 mutants are killed. Survivors: `dup_key_ok` (non-equivalent; a duplicate package key is not a
  documented refusal, the builder tests kill it, as in r1) and `bytecode_written` on 3.9.6 only (equivalent under
  Apple 3.9.6's pycache_prefix).

## New adversarial cases aimed at the fix (expectations from the doc's "Negative transactions are challenged")

- N01 over-refund only; N02 over-credit on an unpaid invoice; N14 both on one invoice: exact paid, refunded,
  invoice amount, credit notes and excess, exit 1. PASS.
- N03 equal amounts: not challenged, exit 0. PASS.
- N04 separate checks, not one combined check: refund 60 plus credit note 60 on a 100.00 invoice paid 100.00, and an
  ordinary credit note on an unpaid invoice. Neither is challenged. PASS.
- N05 whole-book comparison: a refund dated in the period for a payment that lands after period end (before as_of)
  is not challenged. N06 a refund dated after period end still counts toward the excess. PASS.
- N07 cents across many rows (3 x 33.33 paid, 100.00 refunded: excess 0.01). N08 per invoice, no netting across
  invoices. PASS.
- N09 a late refund (loaded after as_of) is excluded from the totals, while a late payment leaves its refund
  challenged (the handback's stated limit). N10 a refund in another currency stays unapplied (currency_mismatch) and
  is not counted. N11 a conflicting refund id is excluded. N12 an exact repeat counts once. N13 a void invoice's
  refund and credit note are never challenged. PASS.
- N16 property test, 40 random books (1 to 5 invoices, payments, refunds and credit notes on both sides of period
  end). PASS.
- N19 (v2) exact reason values `unknown_invoice`, `no_invoice_reference`, `currency_mismatch`,
  `credit_note_before_invoice`, each a backticked name in the doc (r1 P4-1). PASS.
- OBS: O15 controls still close and revenue goes negative as booked (-10.00) with the exceptions; O17 a payment
  dated after as_of but loaded before it counts as paid; O18 an undelivered invoice over-credited by 0.01 is
  challenged. `probes/reason_names.py`: every reason seen in my results is a doc name, except the G13 reader's
  `bad_decimal`, which the doc covers by reference.

## Oracle evolution (disclosed)

v1 of the r2 oracle had 15 core rows. Its first teeth run on 3.13.15 left `r2_reason_renamed` alive (37/39), because no
row pinned the exact reason value. I added N19 from the doc's reason list, positive-controlled it on a copy carrying
that mutant (N19 FAIL, 15/16), and reran the matrix and teeth from scratch. v1 and its results are kept in
`oracle/m14r2_negative_v1.py` and `results/v1/` (not evidence for the verdict).

## Findings

- P3-1 (M14 r1, over-refund and over-credit exit 0): fixed (N01, N02, N06 to N09, N14, N16; K14).
- P4-1 (M14 r1, reason names): fixed (N19, reason probe).
- No new P1 to P4. Doc-stated limits observed as described: a refund ahead of a payment that arrives after as_of is
  challenged until a later run, and only applied payments count.

## Layout

`oracle/` (M14 v3 copy, r2 oracle v2 and v1, helpers, combined), `probes/` (reason names), `scripts/` (matrix,
teeth, fresh caller, builder mutants copy), `results/` (`controls/` base control, `v1/`), `raw/`.
