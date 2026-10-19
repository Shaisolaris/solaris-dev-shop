# G20 - accessible asynchronous search (fixture)

A small search-as-you-type interaction with stale-response protection, a combobox keyboard model, loading, empty and
error states with Retry, and a narrow/wide layout decision. The core is
`employees/engineering/frontend-developer/async_search_core.js`; the role guide is `async-search-ui.md` next to it.

**Unrun:** no browser was started by any check here. Rendering, real keyboard focus, the CSS media query, colour
contrast as rendered and screen-reader output are not verified. The checks run the DOM-free core in JavaScriptCore
(`jsc`, which ships with macOS) and read the demo page as text.

## Files
| File | What it is |
|---|---|
| `demo/index.html` | The interaction on the synthetic fixture: Solaris colours and font, a polite live region, an alert with Retry, aria-busy, a fixture backend with random latency (answers arrive out of order) and a "fail the next request" switch. Open it from disk; it makes no network request. |
| `demo/fixture-data.js`, `fixtures/articles.json` | 240 synthetic help-article titles, written by `make_fixtures.py` (seed 20). Not real content. |
| `oracle_checks.js` | Black-box scenarios o1 to o11 on the public API, with their own virtual clock. |
| `harness.js`, `core_tests.js` | A virtual clock and hand-resolved fetch, and 14 unit tests on the core. |
| `ui_oracle.py` | Runs o1 to o11 in jsc and adds the static demo checks s1 to s6; prints what was not run. |
| `naive_core.js`, `noop_core.js` | Controls the oracle must reject: the usual first draft (last arrival wins, no timeout, arrows stop at the ends) and an API that does nothing. |

## Commands (from the repository root, or from anywhere with the full path)
```bash
python3 examples/capabilities/G20/ui_oracle.py                                  # 17/17 expected, exit 0
python3 examples/capabilities/G20/ui_oracle.py --core examples/capabilities/G20/naive_core.js   # exit 1
python3 examples/capabilities/G20/ui_oracle.py --seed 2026 --scale 10            # unseen sessions, larger run
python3 -m unittest tests.test_g20_capability
```
Exit codes: 0 all checks pass; 1 a check failed; 2 no JavaScript shell, or an invalid argument. Set `G20_JSC` to use
another shell binary.

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
| s1 to s6 | Demo source: a labelled ARIA combobox controlling a listbox with aria-activedescendant; live region, alert, Retry and aria-busy; the CSS breakpoint equals the core's; the demo loads the same core file; no remote URLs; brand colours and font from `assets/social-preview.svg`, focus-visible and reduced-motion rules. |

## Results (macOS jsc, measured here)
| Core | Checks | Stale rows shown (seed 7, scale 1) |
|---|---|---|
| async_search_core.js | 17/17 | 0 |
| naive_core.js | 0/11 | 447 |
| noop_core.js | 0/11 | 132 (it never shows the current results) |

Performance is measured the same way for every core (o11, same seed and scale, same machine, one run each, so treat
small differences as noise). At seed 2026, scale 50 (7,500 sessions; 20,000 key presses over 500,000 options):
async_search_core.js 31 ms for the sessions and 1 ms for the keys, with 0 stale rows shown; naive_core.js 36 ms and
1 ms, with 20,981 stale rows shown. The guard costs nothing measurable here. These are jsc virtual-clock figures,
not browser performance numbers. Log: G20 raw/readme-commands.txt.
