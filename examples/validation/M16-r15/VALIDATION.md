# M16 r15: Grok self-validation of G16 r15 (750c6bc)

Grok self-validation, not independent review. Written by Grok Bot on 2026-10-21, 01:01 to 01:25 PT. The same agent built G16 r15, so this is not independent. The candidate was not modified.

## Verdict: FAIL (P2, P3)
r15 fixes both M16 r14 findings: every M16 r14 row is now correct, and every earlier M16 instrument passes on all four interpreters. Findings are graded on real risk. The one-bare-word residual is P4 when the word is a letter word, as documented. But the lower-case word pattern also accepts digits, so the residual can carry a number next to a topic word ("reply about fee 42"). That contradicts the r15 doc ("it cannot carry ... a number") and is the payload that matters most for numeric questions, so it is P2. A G16 r16 is needed, and the G42 and G24 refreshes stay blocked.

## Binding (raw/binding-verify.txt)
- The candidate is 750c6bc59603a052e094643cdc76e5bf3f2cfd6a, resolved through the GitHub API and git ls-remote. The remote head of review/grok-g16-grounded-evals is that SHA.
- Its one parent is c03423f60d6023468cd377c44b419400726010bc (G16 r14, M16 r14 0766cbc FAIL P2, P3).
- `git diff c03423f 750c6bc` has sha256 026b6c02... and equals G16-r15.patch. It touches 4 files (+82/-4), all in the manifest; all 28 manifest entries match.

## Findings
### P2-1 (fails open, narrow): a number rides the one-word residual
- The lower-case word pattern (`_LW`) is `[a-z0-9]...`, so digits count as lower-case words. These are kept (raw/post-run-number-probes.txt, written after the table run):
  - "AI tools: the team will reply about fee 42."
  - "AI tools: the team will answer on rent 900."
  - T11 "AI tools: the team will answer by noon they say refunds." (table row), and "... by noon they say 42."
- A topic word plus a number is enough for a numeric question to treat the sentence as covering it, and the r15 doc says this residual cannot carry a number. No clause, quote or name can pass.
- Fix direction: lower-case words are letters only. Allow numbers only as a number plus a time unit, or as a clock time after by, at, from, to, until, before or after ("from 9 to 5", "at 8"). In the closing pronoun clause, a reply verb (say, tell, answer, reply) may not appear.

### P3-1 (fails closed): common people phrasing after a bot heading is skipped
- S02 "AI tools: the team will answer within three working days of the request." (of is not in the preposition list).
- S01 "Support bots: the desk will reply to Mr Lee and Ms Tan by Monday." (a title before a name), also end to end (s01).
- S03 "Support bots: the team will reply to Ann, Raj and Mo by Friday." (a list of three names).
- r14 skips all three as well, so this is not a regression from r15. It matters only for people text right after a bot heading, which is rare, and the failure is safe (no answer rather than a wrong one). It is P3 because the cases are ordinary phrasing.
- Fix direction: add of (and with-free prepositions such as among, between, near) to the list, allow Mr, Mrs, Ms, Dr before a name, and allow a comma list of names ending in and or or.

### P4
- The documented one-bare-word residual with a letter word: L06 "reply in kind refunds" and L07 "answer in short paris" are kept. Real risk is low: one lower-case word, no clause, quote, number or capitalised name, so it rarely covers a question. Graded P4 and documented.
- Documented limit: a that or who clause after a noun or person is skipped (L05).
- Carried: a09 over-abstain and documented d01.

### Recorded (not graded)
- L01 skipped, L02 kept, L03 kept, L04 kept (as in r14).

## Instruments (results/)
| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| Full suite (G16 61 + others 84), fresh copy, one Python at a time | 145 OK | 145 OK | 145 OK | 145 OK |
| M16 oracle core / adversarial | 10/10, 17/17 | same | same | same |
| M16 r2 / r3 adversarial | a09, d01 GAP (carried) | same | same | same |
| Builder grounding_oracle | 15/15 | same | same | same |
| M16 r5 to r12 and r14 tables and probes | all hold | same | same | same |
| M16 r13 table | B 11/11, P 8/10 (documented) | same | same | same |
| New M16 r15 table | B 11/12, P 7/10 | same | same | same |
| New M16 r15 e2e | 4/5 (s01) | same | same | same |

- The r15 table JSON is identical on 3.9.6 and 3.13.15.
- Positive controls on the same table: r14 engine B 10/12, P 7/10, e2e 4/5; r8 engine B 12/12, P 0/10, e2e 3/5.
- Stubs: naive 1/15 and noop 0/15.
- x03 ("reply in kind mat", the letter-word residual) holds end to end: the filter keeps the sentence, but it is not cited for "Where is the spare shed key?" because the bare word does not cover the question.

## New rows (oracle/m16r15_table.py, oracle/m16r15_e2e_probes.py)
- Written at 01:01 PT before the first run on any engine (raw/rows-written-before-first-run.txt has their hashes). None come from the builder's rows or tests. The number probes were written after the table run, to grade T11 on real risk.

## Teeth
- Not rerun for this pass: the verdict is FAIL on the table, and the builder's r15 run (46/46 applicable mutants killed on 3.9.6, grok-output/G16 raw/rework-r15) is on the same tree.
