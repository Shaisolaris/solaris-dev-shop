# Market & Competitive Researcher - Learnings (Pending)

## Pending observations
- **2026-04-25 - Clean rebuild from alirezarezvani competitive-intel system**: 5-Layer Intelligence System (Identification → Tracking → Analysis → Output → Cadence) is unusually structured and complete. Codified.
- **2026-04-25 - Win/loss "NOT by AE"** is the most-violated competitive-intel rule that destroys data quality.
- **2026-06-13 - v0.6.0 deep quality pass**: three capabilities the employee prescribed but never tooled got methodology (references/acquisition-and-survey-tooling.md): (1) the Workflow 1 scrape step had no engine/etiquette -> firecrawl(AGPL)/scrapy(BSD)/crawl4ai(Apache) + a polite-crawl contract; (2) SEO-pull + watering-hole discovery assumed search with no engine -> SearXNG(AGPL) vendor-neutral meta-search; (3) Van Westendorp/MaxDiff/Likert were named but had no fielding path -> LimeSurvey(GPL). Reddit code/self-host fallback (PRAW, BSD-2) complements the hosted MCP. Observation worth promoting: the gap pattern here was 'methodology present, acquisition/fielding HOW absent' - the same shape as other employees' depth passes.

## Promotion log
| Date | Rule | Location |
|------|------|----------|
| | | |
## Sources

- Upstream: firecrawl/firecrawl (license not stated: 132,359 (mcp: 6,561)); searxng/searxng (license not stated: 32,021); limesurvey/limesurvey (license not stated: 3,640); praw-dev/praw (license not stated: 4,152); scrapy/scrapy (license not stated: 62,238)
- What was used: noted: firecrawl/firecrawl, searxng/searxng, limesurvey/limesurvey, scrapy/scrapy; methodology absorbed: praw-dev/praw
- License notes: licenses not recorded in scan for: firecrawl/firecrawl, searxng/searxng, limesurvey/limesurvey, praw-dev/praw, scrapy/scrapy - verify before reuse; no code vendored
