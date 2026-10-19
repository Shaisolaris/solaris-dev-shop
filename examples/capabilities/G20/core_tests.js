/* G20 core unit tests (white box on the public API, using harness.js). Run as
 *   jsc employees/engineering/frontend-developer/async_search_core.js examples/capabilities/G20/harness.js core_tests.js
 * Prints "TEST <name> PASS|FAIL|SKIP <detail>" per test, then "DONE <n>". */
(function () {
  "use strict";
  var S = globalThis.SolarisAsyncSearch, n = 0;
  function t(name, fn) {
    var errs; try { errs = fn(); } catch (e) { errs = ["exception: " + (e && e.message ? e.message : e)]; }
    n++;
    if (errs === "skip") { print("TEST " + name + " SKIP this shell has no AbortController"); return; }
    print("TEST " + name + " " + (errs.length ? "FAIL " + JSON.stringify(errs.slice(0, 3)) : "PASS"));
  }
  t("stale_drops_are_counted", function () {
    var e = [], w = H.world();
    w.c.input("ab"); w.advance(150); w.c.input("abc"); w.advance(150);
    w.calls[0].resolve(H.rows("ab", 2)); w.calls[1].resolve(H.rows("abc", 1));
    var s = w.c.state();
    if (s.staleDropped !== 1) e.push("staleDropped " + s.staleDropped);
    if (s.results.length !== 1 || s.results[0].id !== "abc-0") e.push("shown " + JSON.stringify(s.results));
    if (s.requests !== 2) e.push("requests " + s.requests);
    return e;
  });
  t("superseded_request_is_aborted", function () {
    if (typeof AbortController !== "function") return "skip";  // jsc has none; a browser has one (not run here)
    var e = [], aborted = [], w = H.world({ fetch: function (q, o) {
      if (o.signal) o.signal.addEventListener("abort", function () { aborted.push(q); });
      return new Promise(function () {});
    } });
    w.c.input("ab"); w.advance(150); w.c.input("abc"); w.advance(150);
    if (aborted.join() !== "ab") e.push("aborted " + JSON.stringify(aborted));
    return e;
  });
  t("busy_while_newer_text_waits_for_debounce", function () {
    var e = [], w = H.world();
    w.c.input("inv"); w.advance(150); w.calls[0].resolve(H.rows("inv", 2));
    w.c.input("invo");
    var s = w.c.state();
    if (s.status !== "loading" || !s.busy) e.push("listed rows for older text must be marked busy, got " + s.status);
    return e;
  });
  t("timeout_then_late_answer_then_retry", function () {
    var e = [], w = H.world({ timeoutMs: 500 });
    w.c.input("slow"); w.advance(150); w.advance(499);
    if (w.c.state().status !== "loading") e.push("timed out early");
    w.advance(1);
    if (w.c.state().status !== "error" || w.c.state().failedQuery !== "slow") e.push("no timeout error");
    w.calls[0].resolve(H.rows("slow", 1));
    if (w.c.state().status !== "error" || w.c.state().staleDropped !== 1) e.push("late answer not dropped");
    w.c.retry(); w.calls[1].resolve(H.rows("slow", 1));
    if (w.c.state().status !== "results") e.push("retry did not recover");
    return e;
  });
  t("retry_is_a_noop_unless_error", function () {
    var e = [], w = H.world();
    w.c.retry(); w.c.input("x"); w.advance(150); w.calls[0].resolve(H.rows("x", 1)); w.c.retry();
    if (w.calls.length !== 1) e.push("retry outside error made a request");
    return e;
  });
  t("throwing_fetch_is_an_error_state", function () {
    var e = [], w = H.world({ fetch: function () { throw new Error("boom"); } });
    w.c.input("x"); w.advance(150);
    var s = w.c.state();
    if (s.status !== "error" || s.error.indexOf("boom") === -1) e.push(JSON.stringify([s.status, s.error]));
    return e;
  });
  t("rows_are_cleaned_and_capped", function () {
    var e = [], w = H.world({ maxResults: 3 });
    w.c.input("x"); w.advance(150);
    var long = new Array(300).join("y");
    w.calls[0].resolve([{ id: "a", label: long }, { id: "a", label: "dup" }, { id: 5, label: "n" }, { id: "b", label: "B" },
                        { id: "c", label: "C" }, { id: "d", label: "D" }]);
    var s = w.c.state();
    if (s.results.length !== 3 || s.results[0].label.length !== 200) e.push(JSON.stringify(s.results.map(function (r) { return [r.id, r.label.length]; })));
    if (s.rowsDropped !== 3) e.push("rowsDropped " + s.rowsDropped);
    return e;
  });
  t("query_is_truncated_and_trimmed", function () {
    var e = [], w = H.world();
    w.c.input("  " + new Array(400).join("q") + "  "); w.advance(150);
    if (!w.calls.length || w.calls[0].q.length > S.MAX_QUERY || /^\s/.test(w.calls[0].q)) e.push("query sent: " + (w.calls[0] ? w.calls[0].q.length : "none"));
    return e;
  });
  t("min_chars_option", function () {
    var e = [], w = H.world({ minChars: 3 });
    w.c.input("ab"); w.advance(500);
    if (w.calls.length) e.push("searched below minChars");
    w.c.input("abc"); w.advance(150);
    if (w.calls.length !== 1) e.push("did not search at minChars");
    return e;
  });
  t("dispose_stops_everything", function () {
    var e = [], w = H.world();
    w.c.input("x"); w.c.dispose(); w.advance(1000);
    if (w.calls.length) e.push("a request after dispose");
    var v = H.world(); v.c.input("x"); v.advance(150); v.c.dispose(); v.calls[0].resolve(H.rows("x", 1));
    if (v.c.state().status === "results") e.push("a response after dispose was shown");
    return e;
  });
  t("same_query_already_shown_is_not_refetched", function () {
    var e = [], w = H.world();
    w.c.input("teams"); w.advance(150); w.calls[0].resolve(H.rows("teams", 1));
    w.c.input("teams "); w.advance(300);
    if (w.calls.length !== 1) e.push("refetched the same trimmed query");
    if (w.c.state().status !== "results") e.push("status " + w.c.state().status);
    return e;
  });
  t("keys_closed_and_empty", function () {
    var e = [], K = S.listboxKey;
    var r = K({ open: false, active: -1 }, "Enter", 5); if (r.select !== -1 || r.preventDefault) e.push("closed Enter must submit normally");
    r = K({ open: false, active: -1 }, "ArrowUp", 5); if (!r.open || r.active !== 4) e.push("closed ArrowUp opens on the last option");
    r = K({ open: true, active: -1 }, "PageDown", 30); if (r.active !== 9) e.push("PageDown from nothing active lands on option 10, got " + r.active);
    r = K({ open: true, active: -1 }, "PageUp", 30); if (r.active !== 20) e.push("PageUp from nothing active counts from past the end, got " + r.active);
    r = K({ open: true, active: 2 }, "a", 5); if (r.preventDefault || r.active !== 2) e.push("a printable key belongs to the input");
    r = K(null, "ArrowDown", 3); if (!r.open || r.active !== 0) e.push("missing state is treated as closed");
    return e;
  });
  t("announcements_for_clear_and_empty", function () {
    var e = [], N = S.announcement;
    if (N({ status: "results", results: [1], query: "q" }, { status: "idle", results: [], query: "" }) !== "Search cleared.") e.push("clear");
    if (N({ status: "idle", results: [] }, { status: "idle", results: [] }) !== null) e.push("idle twice");
    if (N(null, { status: "empty", results: [], query: "  zzz " }) !== "No results for zzz.") e.push("empty text");
    if (N(null, null) !== null) e.push("null next");
    return e;
  });
  t("layout_boundary_and_targets", function () {
    var e = [], L = S.layoutFor;
    if (L(S.NARROW_MAX_PX).mode !== "narrow" || L(S.NARROW_MAX_PX + 1).mode !== "wide") e.push("boundary");
    if (L(0).mode !== "narrow" || L("800").mode !== "wide") e.push("coercion");
    if (L(1000).minTargetPx < 24) e.push("wide targets under 24px");
    return e;
  });
  print("DONE " + n);
})();
