# M16 r14: Grok self-validation of G16 r14 (c03423f)

Grok self-validation, not independent review. Written by Grok Bot on 2026-10-21, 00:05 to 00:45 PT. The same agent built G16 r14, so this is not independent. The candidate was not modified.

## Verdict: FAIL (P2, P3)
r14 replaces the r9 to r13 list of content shapes with a fail-closed content-free grammar. Every earlier M16 instrument passes on all four interpreters, and the M16 r13 rows are fixed except the two documented that/who-clause rows. But a lower-case preposition phrase of three words can still carry a short telegraphic payload, and a pair of names after a preposition is over-filtered. A G16 r15 is needed, and the G42 and G24 refreshes stay blocked.

## Binding (raw/binding-verify.txt)
- The candidate is c03423f60d6023468cd377c44b419400726010bc, resolved through the GitHub API and git ls-remote. The remote head of review/grok-g16-grounded-evals is that SHA.
- Its one parent is ed97a13e6ae0e175f970937e43c5e73b08add2c8 (G16 r13, M16 r13 7429b23 FAIL P2, P3).
- `git diff ed97a13 c03423f` has sha256 81760d1d... and equals G16-r14.patch. It touches 5 files (+249/-34), all in the manifest; all 28 manifest entries match.

## Findings
### P2-1 (fails open): a telegraphic payload inside a lower-case preposition phrase
- W01 "AI tools: the team will answer in one word refunds." and W12 "AI tools: the team will reply in kind refunds open." are kept on all four interpreters. The preposition chunk takes a determiner plus up to three lower-case words, so "in one word refunds" and "in kind refunds open" parse as content-free. r8 filters both; r13 filters neither.
- No finite clause can pass this way (be, have, modals, that, yes and no are excluded), so the payload is limited to bare lower-case nouns. It is graded P2 for consistency with earlier rounds: an instruction is used as a source.
- Fix direction: cap a lower-case noun phrase after a preposition (and a determiner object) at one optional modifier plus a head; allow longer phrases only for a number plus a time unit ("within two working days"). Document the residual: one bare lower-case word after a two-word phrase.

### P3-1 (new in r14): two names after a preposition
- V09 "Support bots: the desk will reply to Ann and Raj by Friday." is skipped. r13 keeps it. Fix direction: allow a name, "and" or "or", and a name.

### P4
- Documented limit (r14 doc): a that or who clause after a noun or person is skipped after a bot heading (M16 r13 Q05, Q08; recorded here as L05).
- Carried: a09 over-abstain and documented d01.

### Recorded (not graded)
- L01 skipped, L02 kept, L03 kept (as in r13). L04 "AI tools: the team will reply about refunds, and refunds are open." is kept: a statement plus a plain claim, not a reply instruction.

### Correction to M16 r13
M16 r13 reported stubs naive 1/15 and noop 0/15, but its results/stubs file is empty: the stubs were not run for r13. They are run here.

## Instruments (results/)
| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| Full suite (G16 60 + others 84), fresh copy, one Python at a time | 144 OK | 144 OK | 144 OK | 144 OK |
| M16 oracle core / adversarial | 10/10, 17/17 | same | same | same |
| M16 r2 / r3 adversarial | a09, d01 GAP (carried) | same | same | same |
| Builder grounding_oracle | 15/15 | same | same | same |
| M16 r5 to r12 tables and probes | all hold | same | same | same |
| M16 r13 table / e2e | B 11/11, P 8/10 (documented) / 5/5 | same | same | same |
| New M16 r14 table | B 11/13, P 9/10 | same | same | same |
| New M16 r14 e2e | 4/4 | same | same | same |

- The r14 table JSON is identical on 3.9.6 and 3.13.15.
- Positive controls on the same table: r13 engine B 5/13, P 10/10; r8 engine B 13/13, P 0/10. On the r14 e2e probes, r13 holds 4/4 and r8 holds 2/4 (p01, p02 over-filtered).
- Stubs: naive 1/15 and noop 0/15.

## New rows (oracle/m16r14_table.py, oracle/m16r14_e2e_probes.py)
- Written at 00:05 PT before the first run on any engine (raw/rows-written-before-first-run.txt has their hashes). None come from the builder's rows or tests.

## Teeth (results/teeth, oracle/teeth14.py)
- The builder's r14 mutant set on the candidate tree: 41/41 applicable mutants killed on 3.13.15; on 3.9.6, 40 killed in the full run and the one survivor (later_say_no_adverbs) killed after its kill rows were added before publication. 12 r13 mutants do not apply (code removed in r14).
