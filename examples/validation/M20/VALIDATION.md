# M20: Grok self-validation of G20 (accessible asynchronous search, async_search_core.js and demo page)

Grok self-validation by the same bot that built the programme. This is not independent review and not manager acceptance.

- Candidate: G20, commit 8d45038b82a13bf5d360e5969ed2da72b80ce467 on review/grok-g20-async-search (parent 02ba9c5). main stays at 02ba9c5.
- Window: 23:48 to 00:05 PT, 2026-10-18/19. Interpreters 3.9.6, 3.11.16, 3.12.14, 3.13.15. Browser: headless Google Chrome 155.0.8059.80, already installed on this Mac. Nothing was installed. The candidate was not modified.
- Disclosure: the builder of G20 is also Grok Bot. My oracle (oracle/m20_oracle.py, cdp.py) was prepared at 18:13 to 18:33 PT, before G20 existed, from G20.md and M20.md only. Everything written after I saw the candidate is marked as such below.

## Verdict: PASS with residuals (no P1, P2 or P3)
- Stale-response protection, the loading, empty and error states, Retry, the combobox keyboard model, focus behaviour and the 320/360/1280 px layouts all hold.
- These were tested with real key events in a real (headless) Chrome, which the builder did not run.
- What remains is P4 and unrun coverage (screen reader, contrast, other browsers).

## Binding (raw/binding-verify.txt)
- MANIFEST.sha256 has 18 entries, all OK, and its file set equals the diff file set (18 files, +2170/-5).
- The whole-file hash of `git diff 02ba9c5 8d45038` differs from G20.patch only because the patch lists files in another order. All 18 per-file chunks are byte-identical.

## Results
| Instrument | 3.9.6 | 3.11.16 | 3.12.14 | 3.13.15 |
|---|---|---|---|---|
| Builder ui_oracle (jsc) / naive / noop | 17/17, 0/11 (exit 1), 0/11 (exit 1) | same | same | same |
| ui_oracle --seed 2026 --scale 10 | 17/17 | 17/17 | 17/17 | 17/17 |
| tests.test_g20_capability / full suite | 8 OK / 92 OK, 0 skipped | same | same | same |

The browser instruments below are driven from /usr/bin/python3; the browser is the same for every interpreter.

- **Prep oracle in headless Chrome (results/oracle-adapted/, report.json, screenshots):**
  - Core 9/13 as scored. All four failing core rows are save-control rows; see the adjudication below.
  - Adversarial findings: A06 and A08. No external requests; no JS errors.
- **Adjudication of prep-oracle rows, done openly and not re-scored.** My prep oracle assumed a per-result save control. G20.md asks for search, keyboard and focus, the three states and layout, not a save action, and the demo has none.
  - C09, C10 and A08 (failed save, retry save, double save) are **not applicable** to this candidate.
  - C08 fails only on "reached_save". Its other parts pass: Tab reaches the input, there is no trap, and every focused element shows a visible indicator.
  - C11 assumed focus on a result control. The G20 design keeps focus on the input with aria-activedescendant. I covered this with K07 instead.
  - Applicable prep rows: 9/9 core pass, and A01 to A05, A07 and A09 pass.
- **Adapter, disclosed (oracle/make_adapter_m20.py, results/adapter.txt).** The demo has no HTTP backend; it calls an inline `fakeFetch` with random latency, so the oracle could not control response order. I wrote a scratch copy in which only the body of `fakeFetch` (674 chars) calls the oracle's fixture transport. The rest of the page and the core file are byte-identical to the candidate. The page as shipped was tested separately (S01 to S05).
- **Combobox checks, written after seeing G20 (oracle/m20_combobox_checks.py, results/combobox.txt): 15/15.** They use real key events and take their expectations from async-search-ui.md and the page hint.
  - K01: Tab reaches the input, which shows :focus-visible with a 3px outline.
  - K02, K03: ArrowDown sets aria-activedescendant on an existing option and focus stays on the input. ArrowUp wraps; Home and End work.
  - K04: Enter chooses the option, closes the list and keeps focus.
  - K05: Escape closes, then clears.
  - K06: Tab does not select.
  - K07: when results re-render after more typing, focus stays on the input and nothing is left selected.
  - K08: a late older response while an option is active changes no rows and leaves no dangling activedescendant.
  - K09: Retry is reachable by Tab, Enter re-runs the search, and focus returns to the input.
  - K10: keys on an empty list do nothing and throw nothing.
  - S01 to S05 cover the page as shipped, with its own backend: search and choose, the fail switch by keyboard Space, then the alert, then Retry, then recovery. They also check that the final rows match the final text under random latency (one run), with no JS errors and no external requests.
- **Controls (results/control-naive, control-noop):** with naive_core.js or noop_core.js swapped into the adapter, the prep oracle scores 1/13 and the combobox checks 4/15 and 3/15. Disclosed: these controls fail mostly because the demo page needs API calls those cores do not provide (no request is made at all). So they show rejection, not specifically stale-response detection; the teeth below do that.
- **Fresh caller (the prep script; results/fresh-3.9.6/, fresh-3.13.15/; commands hand-transcribed from the README before the run, oracle/fresh-commands-g20.txt):** env -i, a new HOME, a python3 shim and an offline guard.
  - The README commands give 17/17 (exit 0), naive (exit 1), seed 2026 scale 10 17/17 (exit 0) and tests OK, as documented. `--scale banana` gives exit 2.
  - The prep oracle in this environment gives the same 9/13 rows as above. 3.13.15 matches 3.9.6 except for timing.
- **Performance, comparable:** the same oracle method (response release to item text visible, 20 items, over CDP) gives a median of 24.6 ms at 360 px and 25.3 ms at 1280 px (10 reps). My reference stub, measured earlier with the same method, gave 24.2 and 23.3 ms. These are single-machine headless figures that include CDP overhead.

## Teeth (results/teeth/, oracle/teeth_m20.py; written after seeing G20)
- 12 single-anchor mutants of the core and page, scored by the prep oracle plus the combobox checks in headless Chrome. **8/12 are killed.**
  - Killed: stale_guard_off (C07, A03, K08), escape_clear_off (K05), retry_focus_off (K09), label_innerhtml (A05), live_region_off (C04), timeout_off (A06), activedescendant_off (K02, K08), focus_outline_off (K01).
- **Survivors (results/survivor-distinguish.json):**
  - wrap_off: shown non-equivalent. Four ArrowDowns on 3 options select "One A" on the candidate and "Three C" on the mutant. My K03 only tests ArrowUp wrap, which is a gap in my oracle; the builder's o8 covers it.
  - aria_busy_off: shown non-equivalent. aria-busy is "true" while pending on the candidate and "false" on the mutant. My checks accept the "Searching" text as the loading signal.
  - supersede_no_bump: likely equivalent. stopInFlight() already zeroes pending, so the late answer is dropped anyway; the builder reports the same pattern for Clear.
  - onresults_keeps_active: not reachable through this page as far as I found, because typing resets the active option before results arrive. Not proven.
- Observation: the demo repaints the list only when the result count or requestId changes. That is why C06 alone did not catch stale_guard_off (same count and same requestId). With the guard on this is harmless.

## Findings by severity
- P1, P2, P3: none.
- P4: the demo uses timeoutMs 4000, so a 4 s response becomes "Search failed: timed out" (A06). The core default and the doc's usage example are 8000. This is documented behaviour, but the demo times out at half the documented value.
- P4: `G20_JSC` (and an explicit jsc path) that points at a missing binary is silently skipped. ui_oracle.py falls back to the system jsc and reports 17/17 without saying which engine ran. The README says G20_JSC selects another shell.
- P4: row ids become element ids unescaped. An id with spaces gives `id="opt-id-Heron Flats 41"`, which is not a valid HTML id, and it is used as the aria-activedescendant IDREF. It works in Chrome; how assistive technology handles it is unrun.
- Observation: M20.md's "failed saves" challenge has no target, because G20 has no save action. If the owner wants a save flow, that is new scope.
- Observation: the builder's "Unrun" section was accurate for the builder. This pass ran the browser parts in headless Chrome.

## Unrun (labelled, not claimed)
- Screen-reader output (VoiceOver or other): not run.
- Colour contrast as rendered: not measured.
- Browsers other than headless Chrome 155 (Safari, Firefox, mobile, non-headless): not run.
- Touch input, page zoom, forced colours and prefers-reduced-motion as rendered: not run.
- Screenshots (results/oracle-adapted/*.png and fresh-*/oracle/*.png) are visual evidence only. No visual QA claim is made from them. They are kept in the local evidence folder and **not published**, because the publish sanitizer scans text only and I did not change it. Their file names are listed in report.json.

## week-grok hygiene (raw/weekgrok-before.txt, raw/weekgrok-after.txt)
The branch (programme/grok-week-20261018), head 02ba9c5, index c28a2f586b3e3001 and status (ab0ce7884ab30372, 95 lines) are identical at 23:48:56 and 00:01:46 PT. The listings are kept outside this folder.

## Process notes, disclosed
- cdp.py gained Home, End, PageUp and PageDown key codes for the combobox checks. Nothing else in the prep oracle changed.
- The builder run's first full-suite command used an invalid discover form (ImportError). I re-ran it with `discover -s tests -p 'test*.py'` and appended the result to each builder log. I replaced that failed command's traceback in the logs with a one-line note, because it held local interpreter paths that the publish scan flags.
