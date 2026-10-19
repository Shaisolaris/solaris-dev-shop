# M34 validation of G34 (Grok self-validation, NOT independent review)

Candidate: `de76fae516c3aab8adc5df7bfcaac2d751dc92d9` on `review/grok-g34-content-diagnostics`, parent `02ba9c571b10ad1dba792d2ac5534bcad3171e67`.
Validator: Grok. Builder: Grok. This is self-validation by the same agent family that built G34, so it is not independent review.
Window: 2026-10-19 00:05 to 00:17 PT. Candidate checked out as a detached scratch worktree; it was not modified.

## Verdict

PASS with residuals. No P1, P2 or P3 found. Two P4 findings, plus observations.

## Disclosures

- I built my oracle (`oracle/m34_oracle.py`) after G34 landed, from the goal spec (G34.md, M34.md) and the shipped doc
  `content-diagnostics.md`, on my own `kite.example` site. I did not use the builder's fixtures or `diag_oracle.py` to set expectations.
- The teeth use the BUILDER's 40 mutants (`oracle/builder_make_mutants_g34.py`, copied unchanged), scored by MY oracle.
- Harness bugs fixed during the pass, each with the bad run kept: oracle v3 tolerates a tool that writes no `--out`
  (`results/oracle-v1-first-run-3.9.6.txt`); fresh-caller v2 fixes a variable lost in a pipeline subshell
  (`results/fresh-v1-harness-bug-3.9.6.txt`); teeth v2 stops the builder script parsing my argv at import
  (`results/teeth-v1-import-crash/`); teeth v3 counts a change in a row's recorded detail as a kill, v2 counted result only
  (`results/teeth-v2-result-only/`). The builder script prints its mutant list on the first line of each shard log as a side effect.
- Fresh caller: the README commands, with their `/tmp/` paths moved under the fresh folder.
- No installs and no network. Week-grok was recorded before and after and is unchanged.

## Results

| Check | Result |
|---|---|
| Binding | Per-file chunks 59/59 byte-identical with G34.patch (whole-file hash differs only in order). MANIFEST 59/59 OK. Manifest set equals diff set once git path quoting of the non-ASCII fixture name is turned off (`raw/binding-verify.txt`). |
| Builder suite, 4 interpreters (3.9.6, 3.11.16, 3.12.14, 3.13.15) | diag_oracle 14/14, 10 G34 tests OK, full suite 94 OK, snapshot unchanged |
| Grok oracle (C00 clean control, D01 to D31 single defects, X01 to X11 safety), 4 interpreters | 41/43 scored rows, the same on all 4. The 2 FAILs are oracle expectation errors, adjudicated below and not re-scored |
| Controls on Grok oracle | naive 34/43 (fails D17 D18 D19 D25 D30 X04 X06 X07 X10), noop 4/43 |
| Fresh caller (3.9.6, 3.13.15) | exits 1, 0, 1, 0, 1, 1 as documented; after fix: fixed 29, new 0; diag oracle 14/14; scale 2000 pages, 469 findings, 0.22 s; fixtures regenerate identically; no pycache left |
| Teeth (builder's 40 mutants on Grok oracle) | 19/40 killed (18 by result, 1 by detail). All 19 survivors not marked EQUIV fail a builder test, so they are non-equivalent and the gap is in MY oracle. The 2 EQUIV mutants survive both. See `results/teeth-tally.txt`, `results/survivors-builder-tests.txt` |
| Week-grok before and after | identical: head 02ba9c5, index c28a2f586b3e3001, status ab0ce7884ab30372, 95 lines |

## Adjudications (open, not re-scored)

- D25 FAIL: I expected the `sitemap_noindex` finding on the noindex page. The tool keys it on `/sitemap.xml` and names the
  privacy page in the detail. The doc does not say which page. OBS row D25b confirms the finding is present and names the page.
- X07 FAIL: I expected `fixed`, `new`, `persisting` at the top level of the report. The tool nests them under `diff`
  (fixed 1 key, new empty, which is correct). OBS row X07b confirms. Doc wording leans toward top level; see P4-2.

## Findings by severity

- P1: none. P2: none. P3: none.
- P4-1: the doc does not say which page a sitemap finding is reported against (the tool uses `/sitemap.xml`). A caller filtering by page could miss it.
- P4-2: the doc says "the report adds `fixed`, `new` and `persisting` finding keys"; the tool puts them under a `diff` object. Behaviour is fine; the wording should name `diff`.
- OBS: the builder disclosed that `scripts/skill_runtime_contract.py` is missing and that one of its commands ran 13.8 minutes (over the 10-minute guide). Not re-checked here.
- OBS (my oracle, not the candidate): 19 builder mutants survive my oracle (for example title range, anchor via `name`, dir index, unquote, host case, labelledby, hidden inputs, atomic write and temp cleanup). The builder tests kill them.

No proposed-fix patch: none is needed for P4.

## Not run

Live pages and network fetch (the tool is offline by design), real rendering, contrast and screen-reader behaviour,
non-macOS filesystems (case-sensitive link behaviour was checked only on this case-insensitive Mac), very large real sites.
