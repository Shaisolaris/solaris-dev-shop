# G20 - accessible asynchronous search (fixture)

A small search-as-you-type interaction with stale-response protection, a combobox keyboard model, loading, empty and
error states with Retry, and a narrow/wide layout decision. The core is
`employees/engineering/frontend-developer/async_search_core.js`; the role guide is `async-search-ui.md` next to it.

**Rendering (opt-in, not run for this revision):** `browser_checks.py` opens the shipped demo in headless Google Chrome
at 320, 360 and 1280 px CSS widths, drives it with real key events and measures the rendered layout (scrollWidth no
greater than clientWidth for the page and every option). It starts a browser only when `--chrome PATH` or `G20_CHROME`
names one; nothing here discovers or starts a browser by default. The 320 px overflow contract is checked from the
demo source in `tests.test_g20_capability.NarrowLayoutContract`. **Unrun:** screen-reader output, other browsers (Safari, Firefox),
touch, zoom and colour contrast as rendered. `ui_oracle.py` runs the DOM-free core in JavaScriptCore (`jsc`, which
ships with macOS) and reads the demo page as text.

## Files
| File | What it is |
|---|---|
| `demo/index.html` | The interaction on the synthetic fixture: Solaris colours and font, a polite live region, an alert with Retry, aria-busy, a fixture backend with random latency (answers arrive out of order) and a "fail the next request" switch. Open it from disk; it makes no network request. |
| `demo/fixture-data.js`, `fixtures/articles.json` | 240 synthetic help-article titles, written by `make_fixtures.py` (seed 20). Not real content. |
| `oracle_checks.js` | Black-box scenarios o1 to o11 on the public API, with their own virtual clock. |
| `harness.js`, `core_tests.js` | A virtual clock and hand-resolved fetch, and 16 unit tests on the core (including option DOM ids and blank or cut-duplicate row ids). |
| `browser_checks.py` | Rendered checks in headless Chrome over the DevTools protocol (standard library only): layout, keyboard and focus, long labels, option ids and a stale-response regression at 320, 360 and 1280 px. Writes a screenshot per width with `--out`. |
| `ui_oracle.py` | Runs o1 to o11 in jsc and adds the static demo checks s1 to s6; prints what was not run. |
| `naive_core.js`, `noop_core.js` | Controls the oracle must reject: the usual first draft (last arrival wins, no timeout, arrows stop at the ends) and an API that does nothing. |

## Commands (from the repository root, or from anywhere with the full path)
```bash
python3 examples/capabilities/G20/ui_oracle.py                                  # 17/17 expected, exit 0
python3 examples/capabilities/G20/ui_oracle.py --core examples/capabilities/G20/naive_core.js   # exit 1
python3 examples/capabilities/G20/ui_oracle.py --seed 2026 --scale 10            # unseen sessions, larger run
python3 examples/capabilities/G20/browser_checks.py           # no browser named: UNRUN, exit 3, nothing started
python3 -m unittest tests.test_g20_capability
```
Exit codes: 0 all checks pass; 1 a check failed; 2 no JavaScript shell, or an invalid argument. Set `G20_JSC` to use
another shell binary. `browser_checks.py` exits 3 unless `G20_CHROME` or `--chrome` names a binary, and says nothing was run;
with one named it expects 33/33 (exit 0) and exit 1 for `--core naive_core.js`. The unit tests skip the rendered
checks, with that label, unless `G20_CHROME` is set.

## Checks
| Id | Behaviour |
|---|---|
| o1 | Clean control: one request after the 150 ms debounce, loading then results, two announcements. |
| o2 | An older response that arrives after a newer one is never shown, including while the newer text is still in its debounce. |
| o3 | Seven keystrokes 60 ms apart make one request; a trailing space does not make another. |
| o4 | An empty result is the empty state, announced as "No results for X." |
| o5 | A failed request is an error that keeps the query; Retry recovers. No answer within the timeout is an error, the late answer is dropped, and Retry recovers. |
| o6 | Clear returns to idle; a response after Clear is dropped; Clear during the debounce sends nothing. |
| o7 | A non-list response is an error; bad, duplicate and excess rows are dropped (cap). |
| o8 | Keyboard: wrap-around arrows, Home/End, PageDown/PageUp clamped, Enter only with an active option, Escape closes then clears, Tab never selects, keys on an empty list do nothing, new results clear the active option, an out-of-range index is repaired. |
| o9 | Announcements: singular, no repeats for the same state, silent initial idle, error text names the error and Retry. |
| o10 | Layout: narrow to 639 px, wide from 640 px, 44 px narrow targets; bad widths are narrow. |
| o11 | Scale and unseen cases: 150 x scale random sessions (typing, debounce, out-of-order answers, failures, timeouts) never show rows for text other than the current input and end on the right results; 20,000 key presses over 10,000 x scale options stay in range. Timings are printed. |
| NarrowLayoutContract | No browser: the body has `overflow-wrap: anywhere`, no rule sets `white-space: nowrap`/`pre`, `overflow-wrap: normal` or `word-break: keep-all`, no width, min-width, flex-basis or column track demands more than 320 px, the input is 100% wide, one column below the breakpoint; the unrepaired body rule fails the wrap check. |
| L01, L02 (per width, opt-in) | Rendered layout: no horizontal overflow for the document, the listbox or any option, with the 167-character unbroken label shown; one column below 640 px and two at 1280; options at least 44 px tall when narrow. |
| K01 to K07 (per width) | Real keys: Tab reaches the input with a visible 3 px focus ring; aria-activedescendant names an existing, unique, valid id for every option (ids with spaces, tabs, underscores and non-ASCII); the long label stays inside the viewport; arrows wrap, End and Home; Enter chooses and the chosen line does not overflow; Escape closes then clears; Retry works from the keyboard after a failure. |
| S01, X01 (per width) | An older response settled after a newer one changes nothing on screen; no page exceptions and no network requests. |
| s1 to s6 | Demo source: a labelled ARIA combobox controlling a listbox with aria-activedescendant; live region, alert, Retry and aria-busy; the CSS breakpoint equals the core's; the demo loads the same core file; no remote URLs; brand colours and font from `assets/social-preview.svg`, focus-visible and reduced-motion rules. |

## Results (macOS jsc, measured here)
| Core | Checks | Stale rows shown (seed 7, scale 1) |
|---|---|---|
| async_search_core.js | 17/17 | 0 |
| naive_core.js | 0/11 | 447 |
| noop_core.js | 0/11 | 132 (it never shows the current results) |

Rendered checks were not run for this revision (no browser is started by the repair checks). An earlier headless
Chrome run during the repair, on the previous page (8d45038 with only the test transport line added), gave 21/33: at
320 px the long label made the page 1257 px wide (L01), option ids contained spaces and tabs (K02), and the long label
and chosen line ran off screen (K03, K05). That run is the origin of the repair, not evidence for this revision.

Performance is measured the same way for every core (o11, same seed and scale, same machine, one run each, so treat
small differences as noise). At seed 2026, scale 50 (7,500 sessions; 20,000 key presses over 500,000 options):
async_search_core.js 31 ms for the sessions and 1 ms for the keys, with 0 stale rows shown; naive_core.js 36 ms and
1 ms, with 20,981 stale rows shown. The guard costs nothing measurable here. These are jsc virtual-clock figures,
not browser performance numbers. Log: G20 raw/readme-commands.txt.
