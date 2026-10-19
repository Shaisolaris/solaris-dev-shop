# M35 validation of G35 campaign accounting without live spend (Grok self-validation, not independent review)

Candidate: G35 `90da27cf1dd3466e34c89b2c4677b9e35dbaba1e` (branch review/grok-g35-campaign-accounting), direct
parent G14 r2 `6f7b23aa18413907c5fbd250daab475dc94e7a1e` (G13 r3 5666e7b is already its ancestor). Tool
`employees/marketing/paid-ads-manager/campaign_ledger.py`, doc `campaign-accounting.md`. Validator: Grok, the same
agent family that built G35. This is self-validation and does not replace an independent review. Pass window 08:29
to about 09:49 PT, Mon Oct 19 2026.

## Verdict

FAIL (self-validation) on one P2 finding, with one P3 and one P4: **mixed windows are folded silently into spend, CPA and ROAS.** The goal
asks the validator to challenge mixed windows. A proposed fix is included, positive-controlled on a private copy
and **not applied**; it is my own patch. Everything else held, including attribution, dedup, budgets, creatives and
**no contact with any ad platform** (no network import, no ad-platform host string, and an audit hook over every
run logged no socket, DNS, URL, mail or browser use and no child process except the documented G13/G14 calls).

## Prerequisite chain

- The patch sha equals the diff sha (`84320030...13c9`); the manifest has 43/43 entries with 0 mismatches and its set
  equals the diff set. 6f7b23a is the direct parent (raw/binding-verify.txt).
- G14 r2 6f7b23a was validated by M14 r2 at 60682d2; G13 r3 5666e7b by M13 r3 at db6028e. G35 calls both by path; M35
  exercised them only through G35.
- Nothing in the chain is superseded as far as the branch listing shows. The handback notes a textual merge overlap
  with G33 in leadership/cmo (SKILL.md, capability.contract.json, learnings.md); G33 has since moved to r2
  (861167d), which root integration must account for.

## Method

- Fresh oracle `oracle/m35_oracle.py` (v2), written from M35.md, G35.md and the doc before I read the builder's
  oracle. It writes its own packages from scratch (spend and order CSVs under the fixture's G13 contracts, touches,
  conversions, creatives), keeps an independent Decimal model of attribution, spend and ratios, and drives the CLI.
- Core rows:
  - F01 clean control: 30.00 spend, 2 conversions, 75.00 revenue, CPA 15.00, ROAS 2.5000, 270.00 budget left, G14
    difference 0.00, creative ready, caveats explicit.
  - F02 attribution boundaries: a click at exactly 7 days counts and 7 days + 1 s does not; a touch after the
    conversion never counts and one at the same instant does; view window 1 day boundary and 0 = none; a click
    beats a later view; a cross-campaign tie credits neither (`ambiguous_touch`); flight, user and currency held.
  - F03 dedup and value: an identical touch re-send is one copy; a conflicting touch id drops every version and is
    named; pixel + server is one conversion; value comes from the order book with differences listed; a conversion
    without an order is named and worth nothing; test orders, user conflicts and late touches never credit.
  - F04 budgets: spend equal to the daily or total cap is fine and one cent over is named; unknown-campaign spend is
    unassigned and the export identity holds; spend outside the flight is named; float budgets and out-of-range
    windows are refused.
  - F05 ratios: half-even CPA (0.125 to 0.12) and ROAS (0.03125 to 0.0312); null on no conversions and no spend.
  - F06 creatives: claim rounding, unclaimed numbers, publish fields, non-draft status, prohibited wording, unknown
    figures, undisclosed paid connection, social creatives without connection status, held when other findings.
  - F07 cherry-picking: a borrowed figure, a claim not in the copy, an unclaimed percent and "number one" are
    blocked; an order-book window that differs from the package window is refused.
  - **F08 mixed windows**: a spend export over a longer window, or a spend or order contract with another as_of.
  - F09 invalid input and recovery: unknown keys, path escapes, naive times; --out writes report.json and an
    INTERNAL DRAFT brief; an invalid run keeps the earlier report; --out inside the package is refused.
  - F10 seeded soak: 15 random multi-campaign, two-currency packages equal my model per campaign; identities hold.
  - F12 (v2): the finance difference is named and consistent; the doc's own 2.4658 example ("2.47" yes, "2.46" no);
    an existing file outside the package is refused; a late spend row is a gap and not counted; a conversion at the
    window end is not counted; a duplicate campaign id is refused.
  - F11 no ad-platform contact (above).
- Controls: the real tool scores 10/12 (F05 and F08 fail on the findings below); naive_ledger and noop_ledger
  score 1/12 each (only F11, since neither contacts a network). Four interpreters, mutation tests on 3.13.15 and 3.9.6
  with the 38 builder mutants copied unchanged, and a fresh caller. All on rsync copies; the candidate was never
  modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g35: Ran 13 tests in 8.017s  OK  | full: Ran 147 tests in 35.901s  OK  | builder-oracle: ACCEPTED 12/12 | builder-naive: REJECTED 1/12 | builder-noop: REJECTED 0/12 | m35-oracle: M35 ORACLE 10/12 core FAIL | m35-naive: M35 ORACLE 1/12 core FAIL | m35-noop: M35 ORACLE 1/12 core FAIL
== 3.11.16 | g35: Ran 13 tests in 9.735s  OK  | full: Ran 147 tests in 23.133s  OK  | builder-oracle: ACCEPTED 12/12 | builder-naive: REJECTED 1/12 | builder-noop: REJECTED 0/12 | m35-oracle: M35 ORACLE 10/12 core FAIL | m35-naive: M35 ORACLE 1/12 core FAIL | m35-noop: M35 ORACLE 1/12 core FAIL
== 3.12.14 | g35: Ran 13 tests in 7.774s  OK  | full: Ran 147 tests in 25.800s  OK  | builder-oracle: ACCEPTED 12/12 | builder-naive: REJECTED 1/12 | builder-noop: REJECTED 0/12 | m35-oracle: M35 ORACLE 10/12 core FAIL | m35-naive: M35 ORACLE 1/12 core FAIL | m35-noop: M35 ORACLE 1/12 core FAIL
== 3.13.15 | g35: Ran 13 tests in 10.851s  OK  | full: Ran 147 tests in 28.658s  OK  | builder-oracle: ACCEPTED 12/12 | builder-naive: REJECTED 1/12 | builder-noop: REJECTED 0/12 | m35-oracle: M35 ORACLE 10/12 core FAIL | m35-naive: M35 ORACLE 1/12 core FAIL | m35-noop: M35 ORACLE 1/12 core FAIL
pycache in copy: 0
candidate status lines: 0
```

Mutation tests: **v2 oracle 38/38 killed on 3.13.15 and 38/38 on 3.9.6** (results/teeth-*.log). The v1 oracle killed
32/38 on both (results/v1); its six survivors (finance_off, claim_truncate, escape_ok, spend_gaps_ignored,
conv_window_off, dupe_campaign_ok) led to row F12. The builder reports 38/38 with its own tests.

- none

Fresh caller (results/fresh-caller.txt): every line of the README "Run" block, verbatim under `env -i` with a new
HOME and `STATE` a fresh temp folder, on 3.9.6 and 3.13.15: exits 0, 1, 1 and 2 as documented, the builder oracle
ACCEPTED 12/12, naive REJECTED 1/12, noop REJECTED 0/12; --out wrote report.json and campaign-brief.md; no
__pycache__ and the tree is unchanged.

## Findings

- **P2-1: mixed windows are folded silently into spend, CPA and ROAS.** The doc's Limits say "one window and one
  as-of per package", and the tool enforces that for the order contract, but not for the spend contract and not for
  either contract's as_of:
  - A spend contract whose window starts on 2026-08-01 (package window September) with an August spend row of 15.00
    on a campaign whose flight includes August: `reconciled`, exit 0, no finding, spend 35.00 and ROAS 1.1429
    against the September truth of 20.00 and 2.0000.
  - A spend contract with as_of 2026-10-20 (package 2026-10-02) and a spend row loaded on 2026-10-10: exit 0, no
    finding, the late 9.00 is counted (spend 29.00).
  - An order contract with another as_of: exit 0, no finding.
  Proposed fix (`proposed-fix-mixed-windows.patch`, my own, not applied): refuse (exit 2) when the spend contract's
  window or either contract's as_of differs from the package, and say so in the doc. Positive control on a private
  copy (results/fix-positive-control.txt and fix-positive-control-v2.txt): F08 passes, tests.test_g35_capability 13
  OK, the builder oracle ACCEPTED 12/12, the clean fixture still exits 0 and September 1.
- **P3-1: a campaign with conversions and no spend reports CPA "0.00".** The doc: "No conversions or no spend gives
  `null`, never 0 or infinity." With no spend rows for C-a and one attributed conversion, ROAS is null but CPA is
  "0.00", which a creative could then claim. Fix: CPA null when spend is 0.
- **P4-1: prohibited wording is matched as plain substrings, so a dash variant slips through.**
  scripts/probe_prohibited_variants.py (results/probe-prohibited-variants.txt): "Risk-free" and "GUARANTEED" are
  blocked, but "Risk\u2011free" (non-breaking hyphen) and "Risk\u2013free" (en dash) are `ready_for_human_review`.
  A person still reviews every draft and the handback calls the list a safeguard, so P4. Fix: normalize dashes and
  NFKC before matching.
- OBS-2: as the handback says, any other finding holds every creative (`held_unverified`), even in another campaign.

## Disclosures

- The proposed fix is my own patch.
- Oracle v1 to v2: F12 added after the v1 mutation run (v1 kept as oracle/m35_oracle_v1.py, results in results/v1).
  O08 (an OBS row in the first run, kept as results/kept/oracle-first-run-3.9.6.json) became the scored F08 once
  the mixed-window probe showed the silent case.
- Harness incident: I accidentally started a second matrix while the first was still running. I killed both, removed
  their outputs and temp copies, and reran teeth and the matrix once from a clean state; the published results are
  from that single clean run.
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there and its branch, index and status are unchanged.
