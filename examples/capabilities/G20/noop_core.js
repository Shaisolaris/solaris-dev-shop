/* G20 no-op stub: the API exists and does nothing. The oracle must reject it. */
globalThis.SolarisAsyncSearch = {
  createSearchController: function () { var s = { status: "idle", query: "", results: [], error: null, busy: false };
    return { input: function () {}, clear: function () {}, retry: function () {}, state: function () { return s; }, dispose: function () {} }; },
  listboxKey: function (st) { return { open: !!(st && st.open), active: st ? st.active : -1, select: -1, clearInput: false, preventDefault: false, focus: "input" }; },
  onResults: function (st) { return st; },
  announcement: function () { return null; },
  layoutFor: function () { return { mode: "wide", columns: 2, minTargetPx: 32 }; }
};
