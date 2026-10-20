# G20 rendered result (recorded)

One run of `browser_checks.py --chrome "<Google Chrome binary>" --controls --out examples/capabilities/G20/rendered
--timeout 240` on macOS with headless Chrome 155.0.8059.80, 2026-10-19 17:24 to 17:25 PDT. One Chrome process was
started for the whole run (`report.json` "launches": 1; an outside process watch saw one Chrome pid and none left after).

- 33/33 rendered checks pass at 320, 360 and 1280 px (layout, focus ring, option ids, keyboard model, long label,
  stale-response regression, error Retry, no exceptions or network requests).
- Controls in the same session: `naive_core.js` 3/9, `noop_core.js` 3/9, both rejected.
- Screenshots after results are shown (`screenshot-320.png`, `screenshot-360.png`, `screenshot-1280.png`), inspected by
  eye: the 167-character label wraps inside the list at every width, one column below 640 px and two at 1280 px, no
  horizontal scrolling, and the input shows its 3 px focus ring.
- Not run: screen readers, Safari, Firefox, touch, zoom, forced colours.

The run used this revision's code before its final comment-only edits (the header comments of `async_search_core.js`
and `demo/index.html` were updated afterwards to say the rendered run exists); no executable line changed after it.
