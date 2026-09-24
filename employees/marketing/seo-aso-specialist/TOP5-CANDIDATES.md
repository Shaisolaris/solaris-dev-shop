# TOP-5 Verified 2026 Sources - seo-aso-specialist

Scout date: 2026-06-13. All metadata verified live via GitHub API (`api.github.com/repos/...`) on this date. Bar: established/safe, 100+ stars (or 50+ with a notable maintainer), permissive license preferred (GPL/AGPL/NOASSERTION flagged), commit within ~6 months. Gate-0 = grep of ACTUAL employee content (SKILL.md, rules.md, references/, learnings.md, plugin.json), not assumed.

Coverage map of the brief's six areas: technical SEO + GSC tooling (1), GEO/AI-search + schema (2), ASO Play data (3), keyword/SERP volume (4), ASO App Store data (5). Schema/structured-data validation is covered as an honorable mention (best repo is sub-bar on stars) plus folded into the GEO source's JSON-LD checks.

---

## Top 5

| # | Source | Stars | License | Last commit | Maintainer | What it adds | Gate-0 verdict | Tag |
|---|--------|-------|---------|-------------|-----------|--------------|----------------|-----|
| 1 | [AminForou/mcp-gsc](https://github.com/AminForou/mcp-gsc) | 915 | MIT | 2026-04-30 | AminForou (SEO practitioner; 131 forks) | Live Google Search Console analytics over MCP: position-11-20 opportunity pull, cannibalization, period-over-period, batch indexing audit, segmented analytics, destructive-op gate | PRESENT - patterns already lifted into `references/live-search-data-tooling.md` (2026-06-13). Re-verified, not content-duplicate; this entry confirms the source still passes the bar and the CONNECT note is current | CONNECT (patterns already ABSORBED) |
| 2 | [Auriti-Labs/geo-optimizer-skill](https://github.com/Auriti-Labs/geo-optimizer-skill) | 468 | MIT | 2026-06-12 | Auriti Labs (active org; 1309 mocked tests, CI, PyPI `geo-optimizer-skill`) | Research-backed GEO audit RUBRIC: weighted score across robots.txt AI-bot tiers, llms.txt depth, JSON-LD richness, brand/entity coherence, content citability (47 KDD-2024 methods), AI-discovery endpoints, negative-signal + prompt-injection detection. Grounded in Princeton KDD 2024, AutoGEO ICLR 2026, C-SEO Bench 2025 | ABSENT - grep for `princeton/kdd/citability/autogeo/geoready/gptbot/the coding agentbot/perplexitybot` returned 0 hits. Existing `aeo-ai-visibility.md` is high-level prose with no scoring rubric, no AI-bot robots.txt discipline, no research grounding. Genuinely new methodology, not duplicate | ABSORB (METHODOLOGY) |
| 3 | [facundoolano/google-play-scraper](https://github.com/facundoolano/google-play-scraper) | 2888 | MIT | 2026-05-31 | facundoolano (long-standing OSS maintainer; de-facto Play scraper) | Programmatic Play Store metadata/reviews/rankings feed for ASO competitor teardowns + review-sentiment workflows; pairs with sibling `facundoolano/aso` keyword difficulty/traffic scoring | ABSENT - grep `facundoolano/google-play-scraper` returned 0. The ASO playbook is manual-only today. New data-acquisition lane | CONNECT (data layer; METHODOLOGY note for the `aso` difficulty/traffic scoring) |
| 4 | [dataforseo/mcp-server-typescript](https://github.com/dataforseo/mcp-server-typescript) | ~150 | Apache-2.0 | 2026-03-03 | DataForSEO (vendor org) | SERP scrape at scale + keyword search-volume/difficulty + competitor SERP overlap + rank tracking over MCP - the Ahrefs/SEMrush data class via pay-per-call API | PRESENT - already registered in `live-search-data-tooling.md` as the canonical `dataforseo/mcp` CONNECT (PAID). This entry resolves the exact repo path + confirms Apache-2.0 + freshness | CONNECT (PAID - already registered) |
| 5 | [appreply-co/mcp-appstore](https://github.com/appreply-co/mcp-appstore) | 57 | MIT | 2026-04-28 | appreply.co (vendor; notable-maintainer exception to the 100-star bar) | MCP server for App Store + Play Store search/metadata/reviews - batch ASO competitor metadata to feed the teardown + review-management workflows | PRESENT - already registered as ABSORB-watch in `live-search-data-tooling.md`. Still sub-100-star (WATCH tier holds); re-confirmed alive + MIT | CONNECT-WATCH (already registered) |

---

## Honorable mentions / flagged (did NOT make top 5)

- **[adobe/structured-data-validator](https://github.com/adobe/structured-data-validator)** - Apache-2.0, pushed 2026-06-12, but only **13 stars**. Below the star bar; rescued only by the Adobe maintainer name. JS library validating schema.org against Google Rich Results. NOT absorbed as a source - the GEO source (#2) already carries JSON-LD richness checks, and the existing rule already mandates Rich Results Test + schema.org validator. METHODOLOGY pointer noted in the GEO reference instead of a standalone entry. Verdict: WATCH, not absorbed.
- **[google/schemarama](https://github.com/google/schemarama)** - Google-maintained SHACL/ShEx schema validation research project. Notable maintainer but a research artifact, low maintenance cadence; SHACL/ShEx is heavier than client work needs. Verdict: reference-only, not absorbed.
- **[facundoolano/aso](https://github.com/facundoolano/aso)** - 848 stars, MIT, but **last push 2023-11-15 (STALE, >6mo - fails the freshness bar)**. The keyword difficulty/traffic SCORING METHOD is still sound and is captured as METHODOLOGY under source #3; the package itself is not pinned as a live dependency.
- **[ahonn/mcp-server-gsc](https://github.com/ahonn/mcp-server-gsc)** - 224 stars but **license = NOASSERTION (no LICENSE file) - FLAGGED**. AminForou/mcp-gsc (#1) is the cleaner GSC choice (MIT, more stars, more workflows). Not absorbed.
- **Suganthan-Mohanadasan/Suganthans-GSC-MCP** - surfaced in search as "20 tools" but the live repo is **1 star** (search engine conflated it). Fails the bar hard. Not absorbed.

## License flags summary
- All five top sources are permissive (4x MIT, 1x Apache-2.0). No GPL/AGPL in the top 5.
- FLAGGED elsewhere: `ahonn/mcp-server-gsc` = NOASSERTION (no license) - avoid.
- Source #4 (DataForSEO) is Apache-2.0 (permissive) but a **PAID metered API** - cost approval + key required before any run; never speculative bulk pulls.
