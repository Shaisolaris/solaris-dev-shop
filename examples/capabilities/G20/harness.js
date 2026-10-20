/* G20 test harness for JavaScriptCore (jsc) or any JS shell: a virtual clock and a fetch whose responses the test
 * resolves by hand, in any order. Load after the core: load(core); load(harness); then call H.world(options). */
var H = (function () {
  "use strict";
  var drain = typeof drainMicrotasks === "function" ? drainMicrotasks : function () {};
  function world(o) {
    o = o || {};
    var now = 0, timers = [], nextId = 1, calls = [], states = [];
    function schedule(fn, ms) { var id = nextId++; timers.push({ id: id, at: now + ms, fn: fn }); return id; }
    function cancel(id) { timers = timers.filter(function (t) { return t.id !== id; }); }
    function advance(ms) {
      var end = now + ms;
      for (;;) {
        timers.sort(function (a, b) { return a.at - b.at || a.id - b.id; });
        if (!timers.length || timers[0].at > end) break;
        var t = timers.shift(); now = t.at; t.fn(); drain();
      }
      now = end; drain();
    }
    function fetch(q, opt) {
      return new Promise(function (resolve, reject) {
        calls.push({ q: q, resolve: function (v) { resolve(v); drain(); }, reject: function (e) { reject(e); drain(); }, opt: opt });
      });
    }
    var S = globalThis.SolarisAsyncSearch;
    var c = S.createSearchController({ fetch: o.fetch || fetch, schedule: schedule, cancel: cancel,
      debounceMs: o.debounceMs == null ? 150 : o.debounceMs, timeoutMs: o.timeoutMs == null ? 8000 : o.timeoutMs,
      minChars: o.minChars, maxResults: o.maxResults, onChange: function (s) { states.push(s); } });
    return { c: c, calls: calls, states: states, advance: advance, now: function () { return now; } };
  }
  function rows(q, n) { var out = []; for (var i = 0; i < n; i++) out.push({ id: q + "-" + i, label: q + " result " + i }); return out; }
  return { world: world, rows: rows };
})();
