# Market Researcher - TOP-5 Verified 2026 Sources

Researched 2026-06-13. Every figure verified live against the GitHub REST API (repo JSON: stargazers_count, license.spdx_id, pushed_at, archived), not memory. Gate-0 was grepped against this employee's ACTUAL SKILL.md + rules.md + references/ content (not just trigger keywords) - each entry confirms the capability is referenced-but-tool-less, i.e. net-new HOW, not a content duplicate.

Doctrine constraint: this employee gathers EVIDENCE ethically from public sources (rules.md: "Public sources, reviews, filings, job postings, interviews. No pretexting, no scraping behind logins."). So scraping/search tooling is bounded to public, robots-respecting acquisition; survey tooling is the instrument layer under the existing Van Westendorp / MaxDiff / Likert methodology.

Legend: ABSORB = pull methodology into rules/reference; CONNECT = wire as a host-installed tool the researcher drives; METHODOLOGY = extract patterns/discipline, no code bundled. FLAG = copyleft/non-OSI license, absorbed as methodology + self-host note only, never bundled.

| # | Source | URL | Stars | License | Last commit (pushed_at) | Maintainer | What it adds | Gate-0 verdict | Tag |
|---|--------|-----|-------|---------|-------------------------|------------|--------------|----------------|-----|
| 1 | firecrawl/firecrawl (+ firecrawl-mcp-server) | https://github.com/firecrawl/firecrawl | 132,359 (mcp: 6,561) | AGPL-3.0 **FLAG** (mcp-server: MIT, safe) | 2026-06-13 (mcp: 2026-06-09) | Firecrawl (Mendable) | Public-page -> clean LLM-ready markdown at the scrape step Workflow 1 names but never tools: per-page extract, structured/JSON extract, crawl with depth limits, change-tracking (maps to "Change Log of what moved"), robots/rate-limit etiquette. The MIT mcp-server is the CONNECT layer (no AGPL code bundled). | Workflow 1 step 2 says "scrape & extract per page" with ZERO tool/method; grep for firecrawl/crawl4ai/scrapy/headless/robots/rate-limit/markdown = 0 hits. Net-new HOW, not duplicate. | METHODOLOGY (AGPL self-host) + CONNECT mcp (MIT) |
| 2 | searxng/searxng | https://github.com/searxng/searxng | 32,021 | AGPL-3.0 **FLAG** | 2026-06-13 | SearXNG community | Self-hosted privacy meta-search aggregating 70+ engines behind one JSON API - the vendor-neutral SERP/discovery layer for the SEO/market-pull step and watering-hole discovery, without per-vendor SERP-API keys or per-engine ToS scraping. | SKILL Workflow 1 step 4 ("SEO/market pull", "their organic competitors") + Workflow 4 watering-hole discovery assume search but name no engine; grep searxng/serp/meta-search/search-api = 0. Net-new. | METHODOLOGY (AGPL self-host) |
| 3 | limesurvey/limesurvey | https://github.com/limesurvey/limesurvey | 3,640 | NOASSERTION (GPL-2.0+) **FLAG** | 2026-06-12 | LimeSurvey GmbH (>20 yr, notable maintainer) | The only mature OSS survey platform with native research-grade instruments: Van Westendorp PSM as 4 currency items, MaxDiff/conjoint via array+choice question types, Likert matrices, randomization, quotas, branching - the FIELDING layer under the pricing/VOC survey methodology this employee already prescribes. | rules.md prescribes Van Westendorp + MaxDiff + Likert + "<=10 questions, one concept/question, no leading" but gives NO build/field path; grep limesurvey/surveyjs/conjoint/qualtrics/survey-tool = 0. Net-new operational layer. | METHODOLOGY (GPL self-host) |
| 4 | praw-dev/praw | https://github.com/praw-dev/praw | 4,152 | BSD-2-Clause (safe) | 2026-06-13 | praw-dev org (15-yr canonical Python Reddit wrapper) | The code/self-host Reddit acquisition path that complements the already-absorbed hosted reddit-research-mcp: OAuth script-app auth, subreddit/search/comment-tree pulls, rate-limit handling - the fallback when a client cannot use the hosted MCP, with the same evidence-with-receipts discipline. | references/reddit-voc-tooling.md absorbed only the HOSTED MCP ("no creds needed"); grep praw/pushshift/reddit-api/oauth in SKILL+rules = 0. Complementary, not duplicate. | METHODOLOGY + CONNECT (self-host) |
| 5 | scrapy/scrapy | https://github.com/scrapy/scrapy | 62,238 | BSD-3-Clause (safe) | 2026-06-12 | Scrapy / Zyte (15-yr canonical) | Structured, polite multi-page crawling for the deep-profile teardown lane: AUTOTHROTTLE + obey-robots + concurrency caps + per-domain delay (codifies "ethical, public-only" rules.md hard rule), item pipelines that map to the raw-data-persistence folder contract. Permissive baseline crawler vs the AGPL Firecrawl. | Same Gate-0 as #1 (scrape step is tool-less). Listed as the permissive, self-host alternative so the employee is not forced onto an AGPL dependency for basic crawling. Net-new. | METHODOLOGY |

## Honorable mentions (verified, not in top-5)
- **unclecode/crawl4ai** - 66,076 stars, Apache-2.0 (safe), pushed 2026-05-22. Strong permissive LLM-scraper alternative to Firecrawl; folded into the scraping section as the Apache option rather than a separate slot (one scrape lane, two-to-three engines named).
- **surveyjs/survey-library** - 4,775 stars, MIT (safe), pushed 2026-06-13. Excellent for embedding/rendering survey logic in a web app, but LimeSurvey better fits research-grade Van Westendorp/MaxDiff/conjoint fielding for this employee; noted as the MIT in-app option.
- **firecrawl/firecrawl-mcp-server** - 6,561 stars, MIT, pushed 2026-06-09. Counted under #1 as the CONNECT layer (lets the host wire Firecrawl without bundling AGPL code).

## Rejected
- **GeneralMills/pytrends** - 3,715 stars but **ARCHIVED 2024-08**, NOASSERTION, unofficial/scrape-fragile Google Trends wrapper. Stale + unmaintained + ToS-fragile -> rejected (fails the within-~6-months commit bar and the ethical/stable bar).
- **kotartemiy/newscatcher** - last pushed 2020; effectively abandoned -> rejected.

## Flags
- **FLAG (copyleft / non-OSI):** firecrawl (AGPL-3.0), searxng (AGPL-3.0), limesurvey (GPL-2.0+, reported by GitHub as NOASSERTION). All three absorbed as METHODOLOGY + self-host note ONLY; no code copied into the employee. For Firecrawl, the MIT firecrawl-mcp-server is the recommended CONNECT path so the host runs the engine and this repo carries zero AGPL.
- **Safe (permissive):** praw (BSD-2), scrapy (BSD-3), crawl4ai (Apache-2.0), surveyjs (MIT), firecrawl-mcp-server (MIT).
- Auto-deploy does not install external MCP servers; all CONNECT items are host-installed per client (noted in the reference file).

## Sources
- https://github.com/firecrawl/firecrawl
- https://github.com/firecrawl/firecrawl-mcp-server
- https://github.com/searxng/searxng
- https://github.com/limesurvey/limesurvey
- https://github.com/praw-dev/praw
- https://github.com/scrapy/scrapy
- https://github.com/unclecode/crawl4ai
- https://github.com/surveyjs/survey-library
