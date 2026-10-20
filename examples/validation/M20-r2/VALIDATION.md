# M20 r2: G20 r2 and r3 on the current head 0d4db69 (Grok self-validation, not independent review)

Verdict: **PASS.**
- The root finding (a long unbroken label spilled outside the list at 320 px) is fixed, as rendered in Chrome at 320,
  360 and 1280 px.
- Keyboard, focus, option ids and the stale-response regression hold with my own data.
- No P1 to P3.
- This is Grok checking a Grok build. It is not independent review and accepts nothing.

## What is being checked
- M20 validated 8d45038.
- Since then:
  - 174ef33 (r2): narrow layout and option ids at 320 px.
  - 0d4db69 (r3): one Chrome launch covers 320, 360 and 1280 px, and the rendered result is recorded.
- Binding (raw/binding-verify.txt):
  - 0d4db69 is the current remote head of review/grok-g20-async-search.
  - The G20-r3.patch (a format-patch), applied to 174ef33, gives exactly the tree of 0d4db69. The manifest set equals
    the diff set.

## Rendered probe (oracle/m20r2_browser_probe.py): one Chrome launch for the whole pass
- **How the browser was run:**
  - Headless Google Chrome 155.0.8059.85, started once through G20's guarded `Browser` class. It refuses a second
    launch, closes in a finally block, and its watchdog would kill only its own pid.
  - It ran with its own temporary profile. The owner's Chrome was not touched.
  - Launches: 1 (pid 78436). That pid was gone after close.
- **My rows at 320, 360 and 1280 px.** I used 13 rows of my own:
  - blank, empty, digit-first, colon, dot, hash, space, underscore, dash and double-space ids
  - a 180-character CJK label, an 80-emoji label, and a 224-character URL-like label
- **Checks:**
  - **M-L1:** no page overflow, and every option inside the list and the viewport.
  - **M-K1:** ArrowDown through every row. Each active id must be valid and unique.
  - **M-K2:** ArrowUp from the first row wraps to the last.
  - **M-S1:** a newer query answers with no rows, then an older query answers with rows. The empty result must stay.
  - **M-S2:** an older query fails after the newer one succeeded. No error may show, and the rows must stay.
- **First run: 9/15.** All 6 failures were my expectations, not the build. The build follows the documented contract
  in async-search-ui.md:
  - rows with a blank id are dropped, so 11 of my 13 rows are shown
  - labels are cut to 200 characters
- **Re-scored offline from the saved session data, no second launch: 15/15** (oracle/m20r2_rescore.py,
  results/browser-probe-rescored.txt).
  - The corrected K1 checks id validity and uniqueness only. Per-step resolve and selector results were not stored for
    my rows. In the same session, the builder's K02 rows check those properties.
- **Builder's rows, same session:** the builder's own per-width rows (browser_checks.one_width) were reproduced in the
  same session: 33/33. They cover the focus outline, the 167-character label, the columns and target sizes,
  ArrowDown/Home/End/Enter/Escape, the stale response, Retry by keyboard, and no exceptions or network requests.
- **Screenshot review:** I looked at the 320 px screenshot (results/screenshots/m20r2-320.png). The CJK label wraps
  inside the list and nothing spills.

## Builder checks without a browser
- **ui_oracle:** 17/17 on 3.9.6, 3.11.16, 3.12.14 and 3.13.15. The naive core scores 0/11.
- **browser_checks.py with no browser named:** exits 3 and starts nothing.
- **Full suite on fresh clones:** 104 OK (1 skipped: the opt-in browser test) on all four Pythons. Browser processes
  during the suite: 0.

## Residuals
- **P4 (from M20, unchanged):** coverage that was not run. No screen reader, no colour contrast as rendered, no
  browsers other than Chrome.
- **OBS:** rows with a blank id are dropped silently from the list. This is documented. A caller that sends such rows
  gets fewer options without a message.

Browser launches for this pass: 1 (one headless Chrome, closed right after).
