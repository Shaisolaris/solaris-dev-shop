
## 2026-07-24 engineering-core upstream
- Greenfield default Next.js 16 Active LTS (16.2.11+ security line); Next 15 is Maintenance LTS until 2026-10-21.
- Retain WCAG 2.2 AA + CWV floors; add toolchain preflight fail-closed.
- Source: nextjs.org July 2026 security release.
## Sources

- Upstream: GoogleChrome/web-vitals (license not recorded); dequelabs/axe-core (license not recorded); microsoft/playwright (license not recorded); style-dictionary/style-dictionary (license not recorded); TanStack/query (license not recorded)
- What was used: methodology only: GoogleChrome/web-vitals, dequelabs/axe-core, microsoft/playwright, style-dictionary/style-dictionary; methodology absorbed: TanStack/query; connected as external reference: TanStack/query
- License notes: licenses not recorded in scan for: GoogleChrome/web-vitals, dequelabs/axe-core, microsoft/playwright, style-dictionary/style-dictionary, TanStack/query - verify before reuse; no code vendored

## 2026-10-18 G20 asynchronous search (pending)
- A search box that shows "the last response to arrive" shows the wrong results whenever answers come back out of order; the naive stub showed stale rows 447 times across 150 scripted sessions. Keying each response to the newest request id and dropping the rest is what fixed it, not a longer debounce.
- Proposed rule: test async UI with a virtual clock and responses resolved by hand in any order, and label browser, focus and screen-reader behaviour as unrun until a real browser run exists.
