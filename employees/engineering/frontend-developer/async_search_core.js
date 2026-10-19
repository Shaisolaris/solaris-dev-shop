/* Solaris async search core (G20). DOM-free, no dependencies, ES2017.
 * Browser: <script src="async_search_core.js"> defines window.SolarisAsyncSearch.
 * Any JS shell (JavaScriptCore jsc, node): load the file; it defines globalThis.SolarisAsyncSearch.
 *
 * What it guarantees (checked by tests/test_g20_capability.py and examples/capabilities/G20/ui_oracle.py):
 * - Stale-response protection: only the newest request may change the UI. A response for a superseded query,
 *   a response after a clear, and a response after its own timeout are dropped and counted, never shown.
 * - Explicit states: idle, loading, results, empty, error. Error keeps the failed query so retry() re-runs it.
 * - Keyboard model for an ARIA 1.2 combobox with a listbox popup (focus stays on the input; the active option is
 *   exposed with aria-activedescendant): ArrowDown/ArrowUp (wrap), Home/End, PageDown/PageUp, Enter, Escape, Tab.
 * - Live-region announcements on state changes only, never repeated for the same state.
 * - A narrow/wide layout decision that the demo's CSS media query mirrors (40rem = 640px).
 * Browser rendering, real focus movement and screen-reader output are NOT exercised by any check here.
 */
(function (root) {
  "use strict";
  var VERSION = "1.0.0";
  var MAX_QUERY = 200;
  var NARROW_MAX_PX = 639; // wide from 640px (40rem at a 16px root size)
  var PAGE = 10;

  function message(err) {
    var m = err && typeof err.message === "string" ? err.message : String(err);
    return m.slice(0, 200);
  }

  function cleanRows(rows, max) {
    if (!Array.isArray(rows)) throw new Error("bad response: expected a list of results");
    var out = [];
    var seen = Object.create(null);
    for (var i = 0; i < rows.length && out.length < max; i++) {
      var r = rows[i];
      if (!r || typeof r.id !== "string" || typeof r.label !== "string" || !r.id || !r.label) continue;
      if (seen[r.id]) continue; // option ids become element ids: duplicates would break aria-activedescendant
      seen[r.id] = true;
      out.push({ id: r.id.slice(0, 64), label: r.label.slice(0, 200) });
    }
    return { rows: out, dropped: rows.length - out.length };
  }

  function createSearchController(opts) {
    opts = opts || {};
    if (typeof opts.fetch !== "function") throw new TypeError("fetch(query, options) is required");
    if (typeof opts.schedule !== "function" || typeof opts.cancel !== "function") {
      throw new TypeError("schedule(fn, ms) and cancel(handle) are required (pass setTimeout/clearTimeout in a browser)");
    }
    var debounceMs = opts.debounceMs == null ? 150 : Math.max(0, +opts.debounceMs);
    var timeoutMs = opts.timeoutMs == null ? 8000 : Math.max(1, +opts.timeoutMs);
    var minChars = opts.minChars == null ? 1 : Math.max(1, opts.minChars | 0);
    var maxResults = opts.maxResults == null ? 50 : Math.max(1, opts.maxResults | 0);
    var onChange = typeof opts.onChange === "function" ? opts.onChange : function () {};

    var seq = 0;          // id of the newest request; every input() or clear() past debounce bumps it
    var pending = 0;      // id still awaiting its response (0 when none)
    var debounce = null;
    var deadline = null;
    var abort = null;
    var s = { status: "idle", query: "", lastQuery: null, results: [], error: null, failedQuery: null,
              requestId: 0, requests: 0, staleDropped: 0, rowsDropped: 0 };

    function snapshot() {
      return { status: s.status, query: s.query, results: s.results.slice(), error: s.error, failedQuery: s.failedQuery,
               requestId: s.requestId, requests: s.requests, staleDropped: s.staleDropped, rowsDropped: s.rowsDropped,
               busy: s.status === "loading" };
    }
    function emit() { onChange(snapshot()); }
    function stopInFlight() {
      if (deadline !== null) { opts.cancel(deadline); deadline = null; }
      if (abort) { try { abort.abort(); } catch (e) { /* ignore */ } abort = null; }
      pending = 0;
    }
    function settle(id, err, rows) {
      if (id !== seq || id !== pending) { s.staleDropped++; return; } // superseded, cleared or timed out
      stopInFlight();
      if (err) {
        s.status = "error"; s.error = message(err); s.failedQuery = s.lastQuery;
      } else {
        var c;
        try { c = cleanRows(rows, maxResults); } catch (e) { s.status = "error"; s.error = message(e); s.failedQuery = s.lastQuery; emit(); return; }
        s.results = c.rows; s.rowsDropped = c.dropped; s.error = null; s.failedQuery = null;
        s.status = c.rows.length ? "results" : "empty";
      }
      emit();
    }
    function start(q) {
      stopInFlight();
      var id = ++seq;
      pending = id; s.requestId = id; s.requests++; s.lastQuery = q;
      s.status = "loading"; s.error = null;
      emit(); // previous results stay listed while busy; the region is aria-busy
      abort = typeof AbortController === "function" ? new AbortController() : null;
      deadline = opts.schedule(function () { deadline = null; settle(id, new Error("timed out after " + timeoutMs + " ms"), null); }, timeoutMs);
      var p;
      try { p = Promise.resolve(opts.fetch(q, abort ? { signal: abort.signal } : {})); } catch (e) { p = Promise.reject(e); }
      p.then(function (rows) { settle(id, null, rows); }, function (err) { settle(id, err || new Error("request failed"), null); });
    }
    function input(text) {
      var q = String(text == null ? "" : text).slice(0, MAX_QUERY);
      s.query = q;
      if (debounce !== null) { opts.cancel(debounce); debounce = null; }
      var t = q.trim();
      if (t.length < minChars) {
        stopInFlight(); seq++; // a response still on its way for the old text is now stale
        var changed = s.status !== "idle" || s.results.length;
        s.status = "idle"; s.results = []; s.error = null; s.failedQuery = null; s.lastQuery = null;
        if (changed) emit();
        return;
      }
      if (t === s.lastQuery && (pending || s.status === "results" || s.status === "empty")) return; // already shown or on its way
      if (pending) { stopInFlight(); seq++; } // the in-flight answer is for older text: it may never be shown
      if (s.status !== "loading") { s.status = "loading"; s.error = null; emit(); } // listed rows are for older text: mark busy now
      debounce = opts.schedule(function () { debounce = null; start(t); }, debounceMs);
    }
    return {
      input: input,
      clear: function () { input(""); },
      retry: function () { if (s.status === "error" && s.failedQuery) start(s.failedQuery); },
      state: snapshot,
      dispose: function () { if (debounce !== null) { opts.cancel(debounce); debounce = null; } stopInFlight(); seq++; }
    };
  }

  // Keyboard model. st = {open, active}; n = option count. Returns a new state plus what the caller must do.
  function listboxKey(st, key, n) {
    var open = !!(st && st.open) && n > 0;
    var active = open && st.active >= 0 && st.active < n ? st.active : -1;
    var r = { open: open, active: active, select: -1, clearInput: false, preventDefault: false, focus: "input" };
    switch (key) {
      case "ArrowDown":
        if (n === 0) return r;
        r.preventDefault = true;
        if (!open) { r.open = true; r.active = 0; } else { r.active = active < 0 ? 0 : (active + 1) % n; }
        return r;
      case "ArrowUp":
        if (n === 0) return r;
        r.preventDefault = true;
        if (!open) { r.open = true; r.active = n - 1; } else { r.active = active <= 0 ? n - 1 : active - 1; }
        return r;
      case "Home": case "End":
        if (!open) return r; // closed: the key moves the caret in the input
        r.preventDefault = true; r.active = key === "Home" ? 0 : n - 1; return r;
      case "PageDown": case "PageUp":
        if (!open) return r;
        r.preventDefault = true;
        r.active = key === "PageDown" ? Math.min(n - 1, (active < 0 ? -1 : active) + PAGE) : Math.max(0, (active < 0 ? n : active) - PAGE);
        return r;
      case "Enter":
        if (open && active >= 0) { r.preventDefault = true; r.select = active; r.open = false; r.active = -1; }
        return r;
      case "Escape":
        r.preventDefault = true;
        if (open) { r.open = false; r.active = -1; } else { r.clearInput = true; }
        return r;
      case "Tab":
        r.open = false; r.active = -1; r.focus = "next"; return r; // never selects, never traps focus
      default:
        return r;
    }
  }

  // When the option list is replaced, nothing stays active: an index into the old list would point at a different option.
  function onResults(st, n) { return { open: !!(st && st.open) && n > 0, active: -1 }; }

  function announcement(prev, next) {
    if (!next) return null;
    var text;
    switch (next.status) {
      case "loading": text = "Searching"; break;
      case "results": text = next.results.length + (next.results.length === 1 ? " result" : " results") + ". Use up and down arrows to review."; break;
      case "empty": text = "No results for " + next.query.trim() + "."; break;
      case "error": text = "Search failed: " + next.error + ". Retry is available."; break;
      default: text = prev && prev.status !== "idle" ? "Search cleared." : null;
    }
    if (!text) return null;
    if (prev && prev.status === next.status && announcement(null, prev) === text) return null;
    return text;
  }

  function layoutFor(widthPx) {
    var w = +widthPx;
    if (!(w > 0)) w = 320;
    var narrow = w <= NARROW_MAX_PX;
    return { mode: narrow ? "narrow" : "wide", columns: narrow ? 1 : 2, minTargetPx: narrow ? 44 : 32 };
  }

  root.SolarisAsyncSearch = {
    VERSION: VERSION, MAX_QUERY: MAX_QUERY, NARROW_MAX_PX: NARROW_MAX_PX, PAGE: PAGE,
    createSearchController: createSearchController, listboxKey: listboxKey, onResults: onResults,
    announcement: announcement, layoutFor: layoutFor
  };
})(typeof globalThis !== "undefined" ? globalThis : this);
