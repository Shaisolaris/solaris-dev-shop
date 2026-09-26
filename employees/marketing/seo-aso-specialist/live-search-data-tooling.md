# Live Search-Data Tooling - GSC + SERP data + ASO data

Absorbed/connected 2026-06-13. Turns the SEO/ASO methodology from advice-only into live-data-driven. The methodology in `rules.md` and `seo-audit-6-phase.md` is unchanged - this file is the data-acquisition layer that feeds it.

---

## 1. Google Search Console - live analytics (ABSORB: AminForou/mcp-gsc patterns)

Source: AminForou/mcp-gsc (MIT, v0.3.2). Package: `mcp-search-console`. Lifted as workflow patterns; CONNECT the server to run them live (host installs - see CONNECT section).

### Data-state discipline (the one rule that silently corrupts reports)
- GSC serves two data states: `all` (matches the GSC dashboard, includes fresh-but-unconfirmed rows) vs `final` (confirmed only, 2-3 day lag).
- **Default to `all` for trend dashboards** (it matches what the client sees in GSC). **Switch to `final` for any number you commit to in writing** (MoM deltas, exec reporting) so a partial-day tail doesn't read as a drop. State this choice in every report.

### Five GSC workflows to run, not hand-wave
1. **Content opportunities (the highest-ROI query)** - pull queries at **position 11-20 with high impressions and low CTR**. These are page-2 queries one push from page 1: the fastest organic wins. Always run this before recommending new content.
2. **Keyword cannibalization check** - for a query, list every page that ranks for it; when 2+ pages compete, recommend the single canonical page to consolidate to (merge/redirect/de-optimize the losers). Self-competition caps both pages below their ceiling.
3. **Period-over-period comparison** - compare two date ranges per query/page; surface biggest gainers/losers, not just totals. A flat total can hide a winner masking a loser.
4. **Indexing audit** - batch-inspect top ~20 pages (crawl status, last-crawl date, index coverage) and return a prioritized fix list. Patterns across URLs (e.g. a template not indexed) matter more than one-offs.
5. **Filtered analytics** - segment by country / device / query / page. "Mobile US position 11-20" is actionable; a global blended average hides the opportunity.

### Safety
- Destructive ops (add/delete site, delete sitemap) are OFF by default and gated behind an explicit allow-flag (`GSC_ALLOW_DESTRUCTIVE=true`). Keep them off unless a sitemap change is the deliberate task - never enable them for a read/report job.

---

## 2. DataForSEO - SERP + keyword volume data (CONNECT, paid API)

Source: dataforseo/mcp (Apache-2.0). **Paid API - usage-metered. Requires explicit owner cost approval + API key before any run.**
- Use for: SERP scraping at scale, keyword search-volume + difficulty, competitor SERP overlap, rank tracking - the data Ahrefs/SEMrush provide, via API, pay-per-call.
- When: only when client lacks an Ahrefs/SEMrush seat and the job needs hard volume/difficulty numbers. For owned-property performance, GSC (free, first-party) is always preferred over paid SERP estimates.
- Flag the per-call cost in the proposal; do not run speculative bulk pulls.

---

## 3. App Store data - ASO intelligence (ABSORB-watch: appreply-co/mcp-appstore)

Source: appreply-co/mcp-appstore (MIT, low star count - WATCH tier, do not hard-depend).
- Capability gap it fills: programmatic App Store / Play Store metadata + ranking + review pulls to feed the ASO competitor-teardown and review-management workflows (currently done by hand in `aso-audit-playbook.md`).
- Status: reference-only until it matures. Use the manual ASO audit as the baseline; wire this in for batch competitor metadata only if the project volume justifies it.

---

## 4. Play Store / App Store scraping - ASO data feed (CONNECT + METHODOLOGY: facundoolano)

Source: facundoolano/google-play-scraper (MIT, 2888 stars, last push 2026-05-31) + sibling facundoolano/aso (MIT, 848 stars, STALE last push 2023-11-15). Methodology lifted; the scraper is a live CONNECT, the `aso` package is methodology-only (stale, do not pin as a live dependency).

- **Capability:** programmatic Play Store (and, via the sister app-store-scraper, iOS) metadata, ratings, reviews, and search rankings. Feeds the competitor-teardown (step 3) and review-sentiment (step 6) of the ASO audit in SKILL.md - turning the currently-manual teardown into a batch pull.
- **Keyword scoring method (from `facundoolano/aso`, methodology):** for a candidate keyword, derive a **difficulty score** (how hard to rank: a blend of title-match competition, app count, and competitor strength) and a **traffic score** (estimated search popularity), then target keywords with good traffic + moderate difficulty + intent match. This is the concrete version of the "good SP, moderate difficulty, intent match" rule in the ASO keyword-research workflow. Recompute the `aso` scoring logic from the documented method rather than depending on the stale package.
- **When:** project volume justifies batch competitor metadata; otherwise the manual ASO audit stays the baseline (same posture as appreply-co/mcp-appstore in section 3).
- **License:** both MIT - clean. No self-host blocker.

## CONNECT - host install (run on the host; auto-deploy does NOT install external MCP servers)

- **mcp-gsc** (free, MIT): `uvx mcp-search-console`. Auth: Google Cloud OAuth client (Desktop app) JSON via `GSC_OAUTH_CLIENT_SECRETS_FILE`, OR service-account JSON via `GSC_CREDENTIALS_PATH` + `GSC_SKIP_OAUTH=true` (add the SA email as a Full-access GSC user). Keep `GSC_ALLOW_DESTRUCTIVE` unset. Set `GSC_DATA_STATE=final` when generating committed reports.
- **dataforseo/mcp** (PAID - approval + key required): set DataForSEO API credentials per their MCP env. Cost-flag every job.
- **appreply-co/mcp-appstore** (free, MIT, WATCH): defer install until maturity; reference-only for now.
