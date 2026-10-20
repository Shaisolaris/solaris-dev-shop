/* G20 oracle scenarios (black box: only the public SolarisAsyncSearch API). Run by ui_oracle.py as
 *   jsc <core.js> oracle_checks.js -- <seed> <scale>
 * Prints one line per check: "CHECK <id> PASS|FAIL <detail>", then "SCALE <json>". Own clock; does not use harness.js. */
var G20_ARGS = typeof arguments !== "undefined" ? arguments : [];
(function () {
  "use strict";
  var A = G20_ARGS;
  var SEED = +(A[0] || 7), SCALE = +(A[1] || 1);
  var S = globalThis.SolarisAsyncSearch || {};
  var drain = typeof drainMicrotasks === "function" ? drainMicrotasks : function () {};
  var clock = typeof preciseTime === "function" ? function () { return preciseTime() * 1000; } : function () { return Date.now(); };
  function rng(seed) { var x = seed >>> 0 || 1; return function () { x ^= x << 13; x >>>= 0; x ^= x >>> 17; x ^= x << 5; x >>>= 0; return x / 4294967296; }; }
  function World(o) {
    o = o || {};
    var w = this; w.now = 0; w.timers = []; w.id = 1; w.calls = []; w.states = [];
    this.schedule = function (fn, ms) { var id = w.id++; w.timers.push({ id: id, at: w.now + ms, fn: fn }); return id; };
    this.cancel = function (id) { w.timers = w.timers.filter(function (t) { return t.id !== id; }); };
    this.advance = function (ms) {
      var end = w.now + ms;
      for (;;) {
        w.timers.sort(function (a, b) { return a.at - b.at || a.id - b.id; });
        if (!w.timers.length || w.timers[0].at > end) break;
        var t = w.timers.shift(); w.now = t.at; t.fn(); drain();
      }
      w.now = end; drain();
    };
    var fetch = function (q) {
      return new Promise(function (res, rej) {
        w.calls.push({ q: q, ok: function (v) { res(v); drain(); }, fail: function (e) { rej(e); drain(); } });
      });
    };
    this.c = S.createSearchController({ fetch: fetch, schedule: this.schedule, cancel: this.cancel, debounceMs: 150,
      timeoutMs: o.timeoutMs || 5000, maxResults: o.maxResults || 50, onChange: function (s) { w.states.push(s); } });
    this.last = function () { return w.states.length ? w.states[w.states.length - 1] : (w.c.state ? w.c.state() : {}); };
  }
  function rows(q, n) { var out = []; for (var i = 0; i < n; i++) out.push({ id: q.replace(/\W/g, "_") + i, label: q + " #" + i }); return out; }
  function shows(s, q) { return s && (s.status === "results") && s.results.length > 0 && s.results.every(function (r) { return r.label.indexOf(q + " #") === 0; }); }
  var results = [];
  function check(id, fn) {
    var errs;
    try { errs = fn(); } catch (e) { errs = ["exception: " + (e && e.message ? e.message : e)]; }
    results.push(id);
    print("CHECK " + id + " " + (errs.length ? "FAIL " + JSON.stringify(errs.slice(0, 4)) : "PASS"));
  }

  check("o1", function () {
    var e = [], w = new World();
    w.c.input("inv"); w.advance(149);
    if (w.calls.length !== 0) e.push("requested before the debounce elapsed");
    w.advance(1);
    if (w.calls.length !== 1 || w.calls[0].q !== "inv") e.push("one request for 'inv' expected, got " + JSON.stringify(w.calls.map(function (c) { return c.q; })));
    if (w.last().status !== "loading" || !w.last().busy) e.push("no loading/busy state while waiting");
    w.calls[0] && w.calls[0].ok(rows("inv", 3));
    var s = w.last();
    if (s.status !== "results" || s.results.length !== 3) e.push("results not shown: " + s.status);
    var said = [], prev = null;
    w.states.forEach(function (x) { var t = S.announcement(prev, x); if (t) said.push(t); prev = x; });
    if (said.length !== 2 || said[0] !== "Searching" || said[1].indexOf("3 results") !== 0) e.push("announcements " + JSON.stringify(said));
    return e;
  });

  check("o2", function () {
    var e = [], w = new World();
    w.c.input("ca"); w.advance(150);
    w.c.input("cat"); w.advance(150);
    if (w.calls.length !== 2) { e.push("two requests expected, got " + w.calls.length); return e; }
    w.calls[1].ok(rows("cat", 2)); w.calls[0].ok(rows("ca", 9));
    if (!shows(w.last(), "cat")) e.push("an older response replaced the newer one: " + JSON.stringify(w.last().results.slice(0, 1)));
    if (w.states.some(function (s) { return shows(s, "ca"); })) e.push("results for 'ca' were shown after 'cat' was requested");
    // a response for older text that arrives while the newer text is still in its debounce window
    var v = new World();
    v.c.input("ref"); v.advance(150); v.c.input("refund"); v.calls[0].ok(rows("ref", 4));
    if (v.states.some(function (s) { return shows(s, "ref"); })) e.push("results for 'ref' shown although the input already says 'refund'");
    v.advance(150); v.calls[1] && v.calls[1].ok(rows("refund", 1));
    if (!shows(v.last(), "refund")) e.push("final state is not the 'refund' results");
    return e;
  });

  check("o3", function () {
    var e = [], w = new World(), text = "";
    "backups".split("").forEach(function (ch) { text += ch; w.c.input(text); w.advance(60); });
    w.advance(200);
    if (w.calls.length !== 1 || w.calls[0].q !== "backups") e.push("typing 7 characters 60 ms apart made requests " + JSON.stringify(w.calls.map(function (c) { return c.q; })));
    w.c.input("backups "); w.advance(300);
    if (w.calls.length !== 1) e.push("trailing space (same trimmed query, still pending) made another request");
    return e;
  });

  check("o4", function () {
    var e = [], w = new World();
    w.c.input("zzz"); w.advance(150); w.calls[0].ok([]);
    var s = w.last();
    if (s.status !== "empty") e.push("empty result is " + s.status);
    var t = S.announcement(w.states[w.states.length - 2], s);
    if (!t || t.indexOf("No results for zzz") !== 0) e.push("empty announcement " + JSON.stringify(t));
    return e;
  });

  check("o5", function () {
    var e = [], w = new World();
    w.c.input("export"); w.advance(150); w.calls[0].fail(new Error("503"));
    var s = w.last();
    if (s.status !== "error" || s.error.indexOf("503") === -1 || s.failedQuery !== "export") e.push("error state " + JSON.stringify([s.status, s.error, s.failedQuery]));
    w.c.retry();
    if (w.calls.length !== 2 || w.calls[1].q !== "export") e.push("retry did not re-request 'export'");
    w.calls[1] && w.calls[1].ok(rows("export", 2));
    if (!shows(w.last(), "export")) e.push("retry did not recover to results");
    // timeout: no answer within timeoutMs is an error; the late answer is dropped; retry recovers
    var t = new World({ timeoutMs: 1000 });
    t.c.input("slow"); t.advance(150); t.advance(1000);
    if (t.last().status !== "error" || !/time/i.test(t.last().error || "")) e.push("no timeout error: " + t.last().status);
    t.calls[0].ok(rows("slow", 3));
    if (t.last().status !== "error") e.push("a response after its timeout changed the state to " + t.last().status);
    t.c.retry(); t.calls[1] && t.calls[1].ok(rows("slow", 1));
    if (!shows(t.last(), "slow")) e.push("retry after timeout did not recover");
    return e;
  });

  check("o6", function () {
    var e = [], w = new World();
    w.c.input("teams"); w.advance(150); w.c.clear();
    if (w.last().status !== "idle") e.push("clear did not return to idle");
    w.calls[0].ok(rows("teams", 3));
    if (w.last().status !== "idle" || w.last().results.length) e.push("a response after clear was shown");
    var t = S.announcement(w.states[w.states.length - 2], w.states[w.states.length - 1]);
    if (t !== "Search cleared.") e.push("clear announcement " + JSON.stringify(t));
    var v = new World(); v.c.input("x"); v.c.clear(); v.advance(500);
    if (v.calls.length) e.push("clear during the debounce still sent a request");
    return e;
  });

  check("o7", function () {
    var e = [], w = new World({ maxResults: 5 });
    w.c.input("bad"); w.advance(150); w.calls[0].ok({ not: "a list" });
    if (w.last().status !== "error") e.push("a non-list response gave " + w.last().status);
    w.c.retry();
    var r = rows("bad", 8); r.splice(1, 0, { id: "bad0", label: "dup" }, { id: "", label: "x" }, { label: "no id" }, null);
    w.calls[1] && w.calls[1].ok(r);
    var s = w.last();
    if (s.status !== "results" || s.results.length !== 5) e.push("expected 5 clean rows (cap 5), got " + (s.results || []).length);
    var ids = (s.results || []).map(function (x) { return x.id; });
    if (ids.filter(function (x, i) { return ids.indexOf(x) !== i; }).length) e.push("duplicate option ids kept");
    return e;
  });

  check("o8", function () {
    var e = [], K = S.listboxKey, st = { open: false, active: -1 }, r;
    function go(key, n) { r = K(st, key, n); st = { open: r.open, active: r.active }; return r; }
    go("ArrowDown", 5); if (!(st.open && st.active === 0 && r.preventDefault)) e.push("closed ArrowDown should open on the first option");
    for (var i = 0; i < 5; i++) go("ArrowDown", 5);
    if (st.active !== 0) e.push("ArrowDown should wrap to the first option, got " + st.active);
    go("ArrowUp", 5); if (st.active !== 4) e.push("ArrowUp from the first option should wrap to the last, got " + st.active);
    go("Home", 5); if (st.active !== 0) e.push("Home"); go("End", 5); if (st.active !== 4) e.push("End");
    st = { open: true, active: 2 }; go("PageDown", 30); if (st.active !== 12) e.push("PageDown moves 10, got " + st.active);
    st = { open: true, active: 25 }; go("PageDown", 30); if (st.active !== 29) e.push("PageDown clamps, got " + st.active);
    st = { open: true, active: 3 }; go("PageUp", 30); if (st.active !== 0) e.push("PageUp clamps, got " + st.active);
    st = { open: true, active: 3 }; go("Enter", 5); if (r.select !== 3 || st.open || !r.preventDefault) e.push("Enter should select option 3 and close");
    st = { open: true, active: -1 }; go("Enter", 5); if (r.select !== -1 || r.preventDefault) e.push("Enter with nothing active must not select or block form submit");
    st = { open: true, active: 1 }; go("Escape", 5); if (st.open || r.clearInput || r.select !== -1) e.push("Escape when open should only close");
    go("Escape", 5); if (!r.clearInput) e.push("Escape when closed should clear the input");
    st = { open: true, active: 2 }; go("Tab", 5); if (st.open || r.select !== -1 || r.preventDefault || r.focus !== "next") e.push("Tab must close without selecting and let focus move on");
    st = { open: false, active: -1 }; go("ArrowDown", 0); if (st.open || r.preventDefault) e.push("ArrowDown with no options must do nothing");
    st = { open: false, active: -1 }; go("Home", 5); if (r.preventDefault || st.open) e.push("Home when closed belongs to the text caret");
    var o = S.onResults({ open: true, active: 3 }, 7); if (o.active !== -1 || !o.open) e.push("new results must clear the active option");
    o = S.onResults({ open: true, active: 3 }, 0); if (o.open) e.push("no results must close the popup");
    st = { open: true, active: 9 }; go("ArrowDown", 3); if (st.active < 0 || st.active > 2) e.push("an out-of-range active index must be repaired, got " + st.active);
    st = { open: true, active: 9 }; go("ArrowUp", 3); if (st.active < 0 || st.active > 2) e.push("ArrowUp from an out-of-range index, got " + st.active);
    st = { open: true, active: 9 }; go("Enter", 3); if (r.select !== -1) e.push("Enter selected an option that does not exist: " + r.select);
    return e;
  });

  check("o9", function () {
    var e = [], N = S.announcement;
    var res = function (n) { return { status: "results", results: rows("q", n), query: "q" }; };
    if (N(null, res(1)).indexOf("1 result.") !== 0) e.push("singular: " + N(null, res(1)));
    if (N(res(3), res(3)) !== null) e.push("the same results were announced twice");
    if (!N(res(3), res(4))) e.push("a changed count was not announced");
    if (N({ status: "loading", results: [] }, { status: "loading", results: [] }) !== null) e.push("loading announced twice");
    if (N(null, { status: "idle", results: [] }) !== null) e.push("initial idle should be silent");
    var err = N(null, { status: "error", error: "503", results: [] });
    if (!err || err.indexOf("503") === -1 || !/retry/i.test(err)) e.push("error announcement must name the error and the retry: " + err);
    return e;
  });

  check("o10", function () {
    var e = [], L = S.layoutFor;
    [[320, "narrow", 1], [639, "narrow", 1], [640, "wide", 2], [1280, "wide", 2], [NaN, "narrow", 1], [-5, "narrow", 1]].forEach(function (c) {
      var l = L(c[0]); if (!l || l.mode !== c[1] || l.columns !== c[2]) e.push(c[0] + " -> " + JSON.stringify(l));
    });
    if (!(L(320).minTargetPx >= 44)) e.push("narrow touch targets under 44 px");
    return e;
  });

  var scale = {};
  check("o11", function () {
    var e = [], R = rng(SEED), worlds = 150 * SCALE, bad = 0, t0 = clock();
    for (var k = 0; k < worlds; k++) {
      var w = new World({ timeoutMs: 400 + Math.floor(R() * 800) }), words = ["in", "inv", "invo", "invoice", "ref", "refu", "", "re", "tea", "teams"];
      var latest = null, pendingCalls = [];
      for (var step = 0; step < 25; step++) {
        var a = R();
        if (a < 0.45) { latest = words[Math.floor(R() * words.length)]; w.c.input(latest); }
        else if (a < 0.8) w.advance(Math.floor(R() * 300));
        else if (w.calls.length) {
          var i = Math.floor(R() * w.calls.length), call = w.calls[i];
          if (!call.done) { call.done = true; R() < 0.15 ? call.fail(new Error("x")) : call.ok(rows(call.q, 1 + Math.floor(R() * 4))); }
        }
        var s = w.last(), cur = (latest || "").trim();
        if (s.status === "results" && !shows(s, cur)) { bad++; if (e.length < 3) e.push("world " + k + " step " + step + ": showing " + JSON.stringify(s.results[0]) + " for input " + JSON.stringify(cur)); }
      }
      w.advance(400); // let the last debounce fire
      w.calls.forEach(function (call) { if (!call.done) { call.done = true; call.ok(rows(call.q, 2)); } });
      var f = w.last(), cur2 = (latest || "").trim();
      if (cur2 && f.status !== "error" && !shows(f, cur2)) { bad++; if (e.length < 3) e.push("world " + k + " final: " + f.status + " for " + JSON.stringify(cur2)); }
    }
    scale.worlds = worlds; scale.stale_shown = bad; scale.worlds_ms = Math.round(clock() - t0);
    var n = 10000 * SCALE, st = { open: true, active: 0 }, t1 = clock();
    for (var j = 0; j < 20000; j++) { var r = S.listboxKey(st, j % 7 === 0 ? "PageDown" : (j % 3 ? "ArrowDown" : "ArrowUp"), n); st = { open: r.open, active: r.active }; }
    scale.keys = 20000; scale.options = n; scale.keys_ms = Math.round(clock() - t1);
    if (!(st.active >= 0 && st.active < n)) e.push("active index left the list: " + st.active);
    if (scale.keys_ms > 2000) e.push("20000 key presses over " + n + " options took " + scale.keys_ms + " ms");
    return e;
  });
  print("SCALE " + JSON.stringify(scale));
  print("DONE " + results.length);
})();
