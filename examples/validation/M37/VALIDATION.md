# M37 validation of G37 privacy inventory, retention review and request tracing (Grok self-validation, not independent review)

Candidate: G37 `9b0f58e84d3d39828955022d8179c0cf372155a4` (branch review/grok-g37-privacy-inventory), direct parent
G13 r3 `5666e7beb161d1252ddd5dcc0a166aca83255370`. Tool
`employees/legal-compliance/compliance-auditor/privacy_inventory.py`, doc `privacy-inventory.md`. Validator: Grok, the
same agent family that built G37. This is self-validation and does not replace an independent review, and it is
not a compliance certification of anything. Pass window 08:29 to about 09:49 PT, Mon Oct 19 2026.

## Verdict

PASS (self-validation) with two P4 findings and OBS notes. No P1, P2 or P3 findings, so no proposed-fix patch.
The inventory maps the actual fixture fields (including a column G13 ignores), requests trace to exact file and
line, qualified-review dependencies are visible, nothing is deleted, exported or sent, and nothing in the report or
handoff claims compliance, certification or identity verification.

## Prerequisite chain

- The patch sha equals the diff sha (`2e8a5256...56f3`); the manifest has 28/28 entries with 0 mismatches and its set
  equals the diff set. 5666e7b is the direct parent (raw/binding-verify.txt).
- G13 r3 5666e7b was validated by M13 r3 at db6028e (PASS, T1 P4). G37 runs G13 by path; M37 exercised it only
  through G37. Nothing in the chain is superseded as far as the branch listing shows.

## Method

- Fresh oracle `oracle/m37_oracle.py` (v2), written from M37.md, G37.md and the doc before I read the builder's
  oracle. It writes synthetic packages (a G13 contract over orders.csv with a customers.csv dimension, an inventory,
  requests and clocks), keeps its own model of which raw lines hold a subject and when records and requests fall due
  (days, and months clamped to the month end), and drives the CLI. Every run goes through an audit hook (only the
  documented G13 child process is allowed), and every data file is hashed before and after each run.
- Core rows:
  - R01 clean control: complete; R1 finds exactly customers line 2 and orders lines 2 and 4; due 2026-10-10T09:00Z;
    the access package carries the personal fields only; every configured clock goes to qualified review.
  - R02 inventory against the data: a new column and a G13-ignored column are unmapped (the latter marked
    `ignored_by_g13`); a stale entry, a personal field without purpose or basis, an undeclared flow target, a
    personal table without retention or subject key are named; an unknown category is refused.
  - R03 retention: anchor + days at exactly as_of is due and one second later is not; a due record is a
    data-engineer obligation; an unreadable anchor is named and not guessed; a held table's 2018 record (outside
    the G13 metric window) is still due and goes to qualified review.
  - R04 request clocks: Jan 31 + 1 month = Feb 28, Mar 31 + 1 month = Apr 30; 45 days closed on the due instant is on
    time and one second later is `closed_late`; open past due is `overdue_request`; no clock is named and sent to
    qualified review.
  - R05 requests: an unverified request looks nothing up and shows no value; deletion splits into `delete`
    (customers) and `retain_pending_review` (held orders) with both systems in `propagate_to`; correction lists the
    personal fields; no data file changes.
  - R06 request integrity: exact re-sends collapse; the same id with another body is named; the subject matches by
    exact key only (no case, space or prefix match, no free-text search); access finds every held line, including
    an excluded-status row and a row outside the G13 window.
  - R07 output and recovery: --out writes report.json and handoff.md; no compliance, certification or identity
    verification claim; the handoff says not legal advice; an invalid run keeps the earlier report; bad requests
    are rejected and named; --out inside the package, a clock without a source and a path escape are refused.
  - R08 seeded soak: 12 random packages; every request's due time, matched lines and late or overdue findings equal
    my model.
  - R11 (v2): a blank clock source, a real file outside the package and a naive as_of are refused; a subject key
    missing from the data and an inventory table with no data are named; free-text and special-category fields go
    to qualified review.
  - R09 nothing deleted, exported or sent: no network import, no audited event other than G13, and every data file
    byte-identical after every run of the oracle.
- OBS row O10: a request `received_at` without an offset.
- Controls: see the matrix (real tool, naive_inventory and noop_inventory). Four interpreters, mutation tests on
  3.13.15 and 3.9.6 with the 34 builder mutants copied unchanged, and a fresh caller. All on rsync copies; the
  candidate was never modified.

## Results

Matrix (results/pyversions-matrix.txt):

```
== 3.9.6 | g37: Ran 13 tests in 5.730s  OK  | full: Ran 137 tests in 17.585s  OK  | builder-oracle: ACCEPTED 9/9 | builder-naive: REJECTED 0/9 | builder-noop: REJECTED 0/9 | m37-oracle: M37 ORACLE 11/11 core PASS | m37-naive: M37 ORACLE 2/11 core FAIL | m37-noop: M37 ORACLE 2/11 core FAIL
== 3.11.16 | g37: Ran 13 tests in 4.227s  OK  | full: Ran 137 tests in 12.956s  OK  | builder-oracle: ACCEPTED 9/9 | builder-naive: REJECTED 0/9 | builder-noop: REJECTED 0/9 | m37-oracle: M37 ORACLE 11/11 core PASS | m37-naive: M37 ORACLE 2/11 core FAIL | m37-noop: M37 ORACLE 2/11 core FAIL
== 3.12.14 | g37: Ran 13 tests in 4.343s  OK  | full: Ran 137 tests in 13.436s  OK  | builder-oracle: ACCEPTED 9/9 | builder-naive: REJECTED 0/9 | builder-noop: REJECTED 0/9 | m37-oracle: M37 ORACLE 11/11 core PASS | m37-naive: M37 ORACLE 2/11 core FAIL | m37-noop: M37 ORACLE 2/11 core FAIL
== 3.13.15 | g37: Ran 13 tests in 4.249s  OK  | full: Ran 137 tests in 13.548s  OK  | builder-oracle: ACCEPTED 9/9 | builder-naive: REJECTED 0/9 | builder-noop: REJECTED 0/9 | m37-oracle: M37 ORACLE 11/11 core PASS | m37-naive: M37 ORACLE 2/11 core FAIL | m37-noop: M37 ORACLE 2/11 core FAIL
pycache in copy: 0
candidate status lines: 0
```

Mutation tests (results/teeth-*.log): the v1 oracle killed 28/34 on both versions (results/v1); its six survivors
(free_text_not_reviewed, clock_source_optional, escape_ok, naive_asof_ok, subject_key_absent_ok, stale_table_ok)
led to row R11. **The v2 oracle killed 34/34 on 3.13.15 and 34/34 on 3.9.6.** Survivors:

- none

Fresh caller (results/fresh-caller.txt): every line of the README "Run" block, verbatim under `env -i` with a new
HOME and `STATE` a fresh temp folder, on 3.9.6 and 3.13.15: exits 0, 1, 1 and 2 as documented, the builder oracle
ACCEPTED 9/9 and both controls REJECTED 0/9; --out wrote handoff.md and report.json; no __pycache__ and the tree is
unchanged.

## Findings

- **P4-1: a request time without an offset is silently read as UTC.** O10: `received_at` "2026-09-10T09:00:00" is
  accepted with no finding and due 2026-10-10T09:00Z. The tool refuses a naive `as_of`, but the doc does not say the
  same for request times, and a clinic in UTC-7 would get due times 7 hours early. Refuse or name naive request
  times, as for as_of.
- **P4-2 (inherited, flagged by the builder): the role text still says "30-day DSAR".** compliance-auditor SKILL.md
  (HARD NUMBERS, line 72 and the sweep at line 126) and rules.md line 66 say 30 days, while G37's fixture clocks
  and its handback cite one month (GDPR Art. 12(3)). G37 did not introduce this and correctly takes clocks from
  sourced configuration, but a reader of the role gets two numbers. Root or a qualified reviewer should decide the
  wording.
- OBS-1: clock extensions (for example GDPR's two further months) are not modelled; open question 4 in the handback.
- OBS-2: identity is matched by exact key only, with no resolution across keys and no free-text search. That is
  documented in Limits and confirmed by R06; it means a subject recorded under two keys needs two requests.

## Disclosures

- Oracle authoring fix after the first run (kept as results/kept/oracle-authoring-run-3.9.6.json, 8/9): R07
  expected a naive `received_at` and an unknown request type to make the whole package invalid (exit 2). The tool
  names them as `rejected_request_rows` (exit 1) instead, which the doc allows, so R07 now accepts either, and the
  naive-time case moved to the OBS row O10.
- Oracle v1 to v2: R11 added after the v1 mutation run (v1 kept as oracle/m37_oracle_v1.py, results in results/v1).
- Before and after records of week-grok are in raw/weekgrok-before.txt and raw/weekgrok-after.txt: nothing was written
  there and its branch, index and status are unchanged.
