# Top-5 verified 2026 sources - content-marketer depth pass

Research date 2026-06-13. Verified via GitHub REST API (stars, license SPDX, pushed_at, archived). Gate-0 run against this employee's actual files (SKILL.md, rules.md, content-strategy-taste-2026.md) by grep of real content, not assumption.

Scope sweep: SEO content, content ops, editorial standards, repurposing, GEO/AI-search, content analytics.

## The five

### 1. Auriti-Labs/geo-optimizer-skill  -> ABSORB (methodology)
- URL: https://github.com/Auriti-Labs/geo-optimizer-skill
- Stars: 468 | License: MIT (permissive, clean) | Last commit (pushed_at): 2026-06-12 | Maintainer: Auriti Labs (org), active, PyPI-published, 1309 tests, CI green
- What it adds: an OPERATIONAL GEO/AEO audit framework, research-backed (Princeton GEO KDD 2024 arXiv:2311.09735; AutoGEO ICLR 2026 arXiv:2510.11438; C-SEO Bench 2025). The "crawled / understood / cited / monitored" model; an 8-area citability scoring rubric (robots.txt AI-bot allow-list, llms.txt depth, JSON-LD richness, meta, content front-loading, brand/entity Knowledge-Graph links, signals, AI-discovery endpoints); the 47-method citability list (Cite Sources +115%, Statistics +40%, Quotation +41%, Fluency +29% per KDD 2024); negative/anti-citation signals; AI-citation monitoring loop (snapshots + regression). Has an MCP server (geo_audit / geo_citability / geo_schema_validate) Shai could wire up later.
- Gate-0: depth file Section 6 names GEO content PRINCIPLES (summary-first, entity defs, stats-with-sources, comparison tables) and lists "AI-citation presence" as a metric, but has NO operational audit/scoring/monitoring layer, no AI-bot access layer (robots/llms.txt/CDN), no research grounding. NOT a content-duplicate - this is the missing measurement + technical-access half. Verdict: ABSORB methodology (no code bundled; tool itself is MIT so CONNECT-able later).
- Tag: ABSORB / CONNECT (MCP)

### 2. mascanho/RustySEO  -> METHODOLOGY (GPL flagged)
- URL: https://github.com/mascanho/RustySEO
- Stars: 279 | License: GPL-3.0 (FLAG - copyleft; methodology only + self-host note, do not bundle/derive code) | Last commit: 2026-06-09 (fresh) | Maintainer: mascanho, active, Discord, regular releases
- What it adds: the technical content-diagnostics layer a content marketer hands to / co-owns with SEO: shallow + deep crawl, Apache/Nginx LOG analysis (which AI + search bots actually fetched you), Core Web Vitals + PageSpeed, on-page content + keyword-density analysis, keyword clustering, schema generator/validator, topic + content-calendar view, crawl history, GA4/GSC connectors. Frames "free alternative to Screaming Frog / SEMrush" workflow.
- Gate-0: SKILL names "Core Web Vitals integration" + "schema markup" as topics; nothing on crawl/log analysis or AI-bot fetch evidence. No content-duplicate. Verdict: METHODOLOGY (self-host the tool; GPL = do not vendor code).
- Tag: METHODOLOGY (+ self-host note)

### 3. spatie/schema-org  -> CONNECT (tool)
- URL: https://github.com/spatie/schema-org
- Stars: 1493 | License: MIT (permissive) | Last commit: 2026-05-29 | Maintainer: Spatie (established Belgian OSS shop, hundreds of maintained packages)
- What it adds: a production fluent builder that emits valid Schema.org JSON-LD (Article, FAQPage, HowTo, Organization, WebSite, BreadcrumbList) - the executable layer under "schema markup for rich snippets / featured snippets" and a direct input to GEO's "understood" pillar. Code generated from the official Schema.org standard so it tracks the vocab.
- Gate-0: SKILL says "Schema markup for rich snippets" and "Featured snippet + position-zero" as goals but offers no implementation path. CONNECT (named tool for the SEO/dev handoff), not a methodology duplicate.
- Tag: CONNECT

### 4. amplifying-ai/awesome-generative-engine-optimization  -> METHODOLOGY (NOASSERTION flagged)
- URL: https://github.com/amplifying-ai/awesome-generative-engine-optimization
- Stars: 411 | License: none / NOASSERTION (FLAG - treat as all-rights-reserved; cite + link only, do not copy text wholesale) | Last commit: 2026-04-14 (within 6mo) | Maintainer: amplifying-ai (org)
- What it adds: the curated GEO field map - guides, tools, and academic research for AI-search visibility. Use as a living bibliography to keep the GEO section current (it cross-references the same Princeton/AutoGEO research the geo-optimizer encodes). Good for "where is GEO going" scanning, not for lifting prose.
- Gate-0: no curated GEO corpus referenced anywhere in the employee. New connective tissue, not duplicate. Verdict: METHODOLOGY/CONNECT - reference the list, do not copy entries.
- Tag: METHODOLOGY / CONNECT

### 5. marketingtoolslist/awesome-marketing  -> CONNECT
- URL: https://github.com/marketingtoolslist/awesome-marketing
- Stars: 352 | License: MIT (permissive) | Last commit: 2025-08-14 (~10mo - BORDERLINE on the 6mo bar; repo updated_at 2026-06-13, list still maintained) | Maintainer: marketingtoolslist (org)
- What it adds: broad curated marketing/SEO/content/analytics tool index (incl. AI-marketing + SGE categories). A discovery surface when picking content-ops / repurposing / analytics tooling. CONNECT only - it is a pointer list, no methodology to absorb.
- Gate-0: no tool-discovery index in the employee. Not duplicate. Verdict: CONNECT (note the staleness flag on commit cadence).
- Tag: CONNECT

## Rejected (did not make the bar - kept for audit trail)
- brandonhimpfen/awesome-content-marketing - 25 stars (fails 100+). Reject.
- RichardLitt/awesome-styleguides - 736 stars but pushed 2019 + license null; fails 6mo-commit AND flagged license. Reject (stale).
- houtini-ai/geo-analyzer - 21 stars (fails bar). Reject.
- google/schema-dts - 1202 stars, Apache-2.0, but TypeScript type-defs (dev-only, narrower than spatie for content output). Honorable mention; spatie chosen for breadth.
- JDDoesDev/JSON-LD - 10 stars + 2016 push. Reject.

## Flags summary
- GPL-3.0: RustySEO (#2) -> methodology + self-host note only, no code vendoring/derivation.
- NOASSERTION / no license: awesome-generative-engine-optimization (#4) -> cite/link only, no text copy.
- Stale-commit borderline: awesome-marketing (#5) -> ~10mo since push; CONNECT-only so low risk.
- Clean MIT: geo-optimizer-skill (#1), spatie/schema-org (#3).
