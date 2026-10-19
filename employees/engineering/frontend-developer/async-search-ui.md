# Accessible asynchronous search (G20)

`async_search_core.js` is a dependency-free, DOM-free core for a search-as-you-type combobox. It was built against
the synthetic fixture in `examples/capabilities/G20/` and is checked there. Browser behaviour has NOT been run by any
check: rendering, real focus movement, the CSS media query and screen-reader output are untested. The checks run the
core in JavaScriptCore (`jsc`) with a virtual clock, and they read the demo page as text.

## What the core guarantees
- **Stale-response protection.** Every request gets an id, and only the newest may change the UI. A response for older
  text, a response after Clear, a response after its own timeout and a response after `dispose()` are dropped and
  counted in `staleDropped`. While newer text waits for its debounce, the listed rows are marked busy.
- **States.** `idle`, `loading` (`busy: true`, previous rows stay listed), `results`, `empty`, `error`. An error keeps
  `failedQuery`, and `retry()` re-runs it; `retry()` does nothing in any other state. A fetch that throws, rejects,
  returns a non-list or does not answer within `timeoutMs` is an error.
- **Input hygiene.** Queries are trimmed and cut to 200 characters. Rows need a non-empty string id and label; duplicate
  ids are dropped (option ids become element ids for `aria-activedescendant`), labels are cut to 200 characters, and
  at most `maxResults` are kept. `rowsDropped` counts the rest.
- **Keyboard model (`listboxKey`)**, ARIA 1.2 combobox with a listbox popup, focus always on the input:
  ArrowDown/ArrowUp open the list or move with wrap-around; Home/End and PageDown/PageUp (10, clamped) work only while
  the list is open, otherwise they belong to the caret; Enter selects only when an option is active (otherwise the form
  submits normally); Escape closes, and a second Escape clears; Tab closes without selecting and lets focus move on.
  New results clear the active option (`onResults`), because an old index would point at a different option.
- **Announcements (`announcement`)** for a polite live region: "Searching", "N results.", "No results for X.",
  "Search failed: E. Retry is available.", "Search cleared." Never the same text twice in a row for one state.
- **Layout (`layoutFor`)**: narrow up to 639 px (one column, 44 px targets), wide from 640 px (two columns, 32 px
  targets). The demo's `@media (min-width: 40rem)` mirrors it at a 16 px root size.

## Using it
```html
<script src="async_search_core.js"></script>
<script>
const c = SolarisAsyncSearch.createSearchController({
  fetch: (q, { signal }) => fetch(`/search?q=${encodeURIComponent(q)}`, { signal }).then(r => r.json()),
  schedule: (fn, ms) => setTimeout(fn, ms), cancel: h => clearTimeout(h),
  debounceMs: 150, timeoutMs: 8000, onChange: render });
input.addEventListener("input", () => c.input(input.value));
</script>
```
`examples/capabilities/G20/demo/index.html` is a complete page on the fixture (Solaris colours and font from
`assets/social-preview.svg`), with a synthetic backend whose latency is random, so answers arrive out of order. It
also has a "fail the next request" switch.

## Checks
```bash
python3 examples/capabilities/G20/ui_oracle.py            # 11 behaviour checks in jsc + 6 static demo checks
python3 -m unittest tests.test_g20_capability
```
`ui_oracle.py` exits 2 when no JavaScript shell is found, and its report always lists what was not run.

## Limits
- No browser was run. Treat keyboard, focus, contrast and screen-reader behaviour in the demo as unverified until
  someone runs it in real browsers with assistive technology. `--sol-ink-2` is not a brand colour, and its contrast was
  not measured.
- JavaScriptCore has no `AbortController`, so aborting a superseded request is skipped in the checks (reported as SKIP).
  Without one, a superseded response is still dropped, but the network request is not cancelled.
- Performance figures come from the virtual-clock run in jsc (milliseconds for 150 to 7,500 simulated sessions and
  20,000 key presses). They say the core is cheap, not how a page performs in a browser.
