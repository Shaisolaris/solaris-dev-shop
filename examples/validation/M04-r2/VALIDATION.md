# M04 r2: G04 r2 and r3 on the current head e9fa278 (Grok self-validation, not independent review)

Verdict: **PASS after one repair.**
- The first run on G04 r2 155fc33 found a P2. The repair was a fast-forward builder fix, G04 r3 e9fa278. This
  recheck passes on it.
- M04 P3 (owner conflict) is closed. M04 P4-1 is unchanged.
- This is Grok checking a Grok build. It is not independent review and accepts nothing.

## What is being checked
- M04 validated 314b4db.
- Since then:
  - 155fc33 G04 r2: the owner bound into the activate and brief receipt inputs (root finding: a same-revision owner
    change reused a brief naming the old owner).
  - e9fa278 G04 r3: the repair below.
- Binding (raw/binding-verify.txt):
  - e9fa278 is the current remote head of review/grok-g04-handoff.
  - The G04 r3 patch equals `git diff --binary 155fc33 e9fa278`. The manifest matches.

## Probe written for this pass (oracle/m04r2_probe.py)
Black-box CLI only, on the shipped fixture copy.
- **Q1:** owner changed at the `--stop-after brief` point (the root finding).
- **Q2:** owner changed after activate.
- **Q3:** owner changed after revision 1 was delivered.
- **Q4:** a crash after the delivery effect (exit 75), then the owner is changed and another worker resumes.
- **Q5:** owner changed and changed back before delivery.
- **Q6:** control, same-owner rerun.
- **Q7:** control, revision 2 with a new owner.
- **Q8:** a non-ASCII owner.
- **Q9:** an order delivered by G04 r1 314b4db, rerun by the new tool with the same owner. The deliver step is reused
  and there is no second delivery.

Results:

| Head | Probe score | Failing rows |
|---|---|---|
| G04 r3 e9fa278 | 9/9 on 3.9.6, 3.11.16, 3.12.14, 3.13.15 | none |
| G04 r2 155fc33 | 7/9 | Q3, Q4 |
| G04 r1 314b4db | 3/8 (no Q9) | the root finding rows |

## Finding on G04 r2, fixed in G04 r3
- **P2-1: an owner change after delivery delivered the same revision twice.**
  - On 155fc33, changing the owner after revision 1 was delivered made the activate, brief and deliver receipts
    stale. The brief was re-rendered, its hash gave a new delivery key, and a second ledger record for revision 1
    was appended under the new owner (exit 0, ledger 2).
  - The same happened after a crash between the delivery and its receipt (Q4).
  - The contract is one delivery per order revision, and the docstring calls the delivery "the effect that must
    never be duplicated".
  - G04 r1 did not deliver twice, so this was introduced by the r2 fix.
  - Repair: G04 r3 e9fa278 (see grok-output/G04-r3).
    - Such an owner change is refused with exit 2 before anything is written, and it is checked again under the
      ledger lock.
    - The new test fails on 155fc33. The r2 test was moved to the stop-after-brief point (disclosed).

## Earlier and builder checks on e9fa278
- **M04 oracle (my M04 oracle, unchanged):** 14/16 on all four Pythons. The two rows that fail are the same C02 and
  C14 as in M04: C02 was my own harness error, and C14 is P4-1.
- **handoff_oracle:** 16/16 on all four Pythons. naive scores 9/16 and no-op 1/16 (results/builder-oracle.txt).
- **G04 tests:** 15 OK.
- **Full suite on fresh clones:** 146 OK on all four Pythons. Browser 0 (results/full-suite-matrix.txt).

## Residuals
- **P4-1 (from M04, unchanged):** an exit-2 refusal still creates the empty `.handoff/<order>/.worker.lock` when the
  folder is new. The new owner refusal writes nothing to the journal or the ledger.
- **OBS:** the delivery record names the owner, but a receiver that wants the owner history must read revisions in
  order. That is by design.

Browser launches for this pass: 0.
