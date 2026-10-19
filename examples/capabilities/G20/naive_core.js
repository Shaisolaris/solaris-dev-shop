/* G20 naive stub: the common first draft. Every keystroke fetches at once, every response is shown when it arrives
 * (last arrival wins), no timeout, errors stay until the next keystroke, and the arrow keys stop at the ends. */
globalThis.SolarisAsyncSearch = {
  createSearchController: function (o) {
    var s = { status: "idle", query: "", results: [], error: null, failedQuery: null, requestId: 0, requests: 0, busy: false };
    function emit() { o.onChange && o.onChange({ status: s.status, query: s.query, results: s.results.slice(), error: s.error, failedQuery: s.failedQuery, busy: s.status === "loading", requestId: s.requestId }); }
    function go(q) {
      s.status = "loading"; s.requests++; s.requestId++; emit();
      Promise.resolve(o.fetch(q, {})).then(function (rows) {
        s.results = Array.isArray(rows) ? rows : []; s.status = s.results.length ? "results" : "empty"; emit();
      }, function (err) { s.status = "error"; s.error = String(err && err.message); s.failedQuery = q; emit(); });
    }
    return {
      input: function (t) { s.query = String(t); if (!s.query.trim()) { s.status = "idle"; s.results = []; emit(); return; } go(s.query.trim()); },
      clear: function () { s.query = ""; s.status = "idle"; s.results = []; emit(); },
      retry: function () { if (s.failedQuery) go(s.failedQuery); },
      state: function () { return s; }, dispose: function () {}
    };
  },
  listboxKey: function (st, key, n) {
    var a = st.active, open = st.open, r = { open: open, active: a, select: -1, clearInput: false, preventDefault: true, focus: "input" };
    if (key === "ArrowDown") { r.open = true; r.active = Math.min(n - 1, a + 1); }
    else if (key === "ArrowUp") { r.active = Math.max(0, a - 1); }
    else if (key === "Enter") { r.select = a; r.open = false; }
    else if (key === "Escape") { r.open = false; }
    return r;
  },
  onResults: function (st) { return st; },
  announcement: function (p, n) { return n.status === "results" ? n.results.length + " results" : n.status; },
  layoutFor: function (w) { return w < 768 ? { mode: "narrow", columns: 1, minTargetPx: 32 } : { mode: "wide", columns: 2, minTargetPx: 32 }; }
};
