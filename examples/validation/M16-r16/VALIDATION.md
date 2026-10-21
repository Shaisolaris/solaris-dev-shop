# M16 r16: validation of G16 r16

Grok self-validation, not independent review. This does not accept G16. Acceptance comes only from root QA.

- Candidate: G16 r16 `661f7df40a61b23b287bedd6afebf9c70441bf66` on `review/grok-g16-grounded-evals` (parent `750c6bc59603a052e094643cdc76e5bf3f2cfd6a`).
- Binding: remote head, gh API head and parent, local checkout, diff hash equal to `G16-r16.patch` hash, manifest 28/28 with no mismatches, all four changed files in the manifest, main `02ba9c5` untouched. See `raw/binding-verify.txt`.
- Rows: `oracle/m16r16_table.py` and `oracle/m16r16_e2e_probes.py` were written and hashed at 01:33:14 PDT before any engine ran (`raw/rows-written-before-first-run.txt`).

## Verdict: FAIL (1 P2, 1 P4)

## Results

| Instrument | r16 candidate | r15 control | r8 control |
|---|---|---|---|
| M16 r16 table, bot-addressed filtered | 12/12 on 3.9.6, 3.11, 3.12, 3.13 | 12/12 | 12/12 |
| M16 r16 table, people kept | 10/10 on all four | 3/10 | 0/10 |
| M16 r16 end-to-end probes | HOLDS 5/5 on all four | 4/5 (gap j02) | 3/5 |
| Prior tables M16 r6-r15 and e2e | all hold on all four; M16 r13 table P 8/10 is the documented, previously adjudicated split (same as r14 and r15 runs) | | |
| M16 r4 instruments (o1-o15) | 15/15 on all four | | |
| Stubs (control) | naive 1/15, noop 0/15 | | |
| Teeth (G16 r16 mutant set, run on 3.13.15) | 53 killed, 0 survived; 12 stale mutants for code retired in r14 did not apply (builder run had 17 before re-pointing 5) | | |

Table JSON is byte-identical on 3.9.6 and 3.13. The pre-written rows all pass; the r16 fixes for clock times, titles, name lists and the four new prepositions behave as described.

## Findings

### F1 (P2): a number still reaches a cited answer through two routes the r16 number rule does not cover

Found in post-run exploratory probes (`raw/post-run-exploratory-probes.txt`, `raw/post-run-number-e2e.txt`), so they are marked post-run, not pre-written.

1. Name tag. `_NAME1` accepts a trailing tag of up to three capitals or digits, or any number (meant for "Room 12", "Hall B"). A capitalised topic word therefore carries a number: `AI tools: the team will reply about Fee 42.` is kept, and end to end `What is the fee?` is answered from that sentence. `AI tools: the team will reply about Rent 900 on time.` answers `How much is the rent?` the same way. `... reply near Ann and Bob 42.` is also kept.
2. Time clause. The `until/when/before/after` clause branch takes free clause words that may include digits, so `AI tools: the team will reply until the fee is 42.` and `... answer until fee 42.` are kept.

Risk: this is the same class as the M16 r15 P2 (a bot-addressed sentence carrying a topic word plus a number that gets cited), now needing a capital letter or a time-clause opener. It answers end to end, so it is graded P2, not P4.

Suggested fix for G16 r17: allow a digit tag on a name only after a place head word (Room, Hall, Gate, Floor, Level, Unit, Suite, Block, Bay, Platform, Building, Desk) and otherwise only a single capital letter; make the time-clause words letters-only with clock times as the only number allowed; add these rows plus an end-to-end probe.

### F2 (P4): a bare name after a preposition is kept

`AI tools: the team will answer to Mr Paris.` is kept. A person's name after "to" is indistinguishable from real people text, carries no clause, quote or number, and is not an asserted answer. Documented residual class; P4.

## Next step

G16 r17 with the F1 fix, then M16 r17. G42 r6 and G24 refresh stay blocked until an M16 pass has nothing above P4. Release stays NOT_READY.
