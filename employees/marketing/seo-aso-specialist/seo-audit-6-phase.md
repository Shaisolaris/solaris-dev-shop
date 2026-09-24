# 6-Phase SEO Audit

Run on every new SEO engagement before any recommendations. Output: the SaaS Health Report deliverable.

## Phase 1 - Crawl + Technical
- Screaming Frog OR Sitebulb crawl, full site
- robots.txt + XML sitemap validation (sitemap vs indexed count > 20% gap = drift)
- Canonical tag audit (point to non-indexed = broken)
- Redirect chains audit (301 chains > 2 hops = link equity leak)
- Core Web Vitals from CrUX + PageSpeed Insights (LCP < 2.5s, INP < 200ms, CLS < 0.1)
- Mobile usability (Lighthouse + Search Console mobile usability report)
- HTTPS coverage + HSTS check
- JS rendering audit (does Googlebot see content? compare crawl with JS on vs off)
- Server log-file analysis (large / parameter-heavy sites only): verify bots by IP, group crawl by template, find crawl waste + orphan pages + bot-only 5xx, set the three-way AI-crawler robots.txt strategy (see `elite-technical-geo-2026.md`)

## Phase 2 - On-Page
- Title tag per URL (50-60 chars, keyword-forward, no duplicates)
- Meta description per URL (150-160, CTR-optimized, NOT a ranking factor)
- H1 (one per page) + H2/H3 hierarchy check
- Content depth vs top-3 ranking competitors (word count + topical coverage)
- Internal linking graph (orphaned pages, internal anchor text patterns, hub-and-spoke completeness)
- Image alt text coverage
- Schema markup audit (which types present, which are valid per Rich Results Test)

## Phase 3 - Content
- Keyword ranking distribution: top 3 / top 10 / top 50 / top 100
- Keyword gaps vs top 3 competitors (Ahrefs / SEMrush)
- Content freshness - last-modified date per URL, identify decaying content
- E-E-A-T signals (author bios, author schema, expert citations, original research)
- Branded search volume trend (leading indicator of brand health)

## Phase 4 - Off-page
- Backlink profile: DR, referring domains, anchor text distribution
- Toxic links (low-DR, irrelevant TLDs, exact-match anchor over-optimization)
- Brand mentions (linked + unlinked)
- Disavow file status

## Phase 5 - AI visibility (AEO/GEO)
- Test top 20 brand + category queries on ChatGPT / Perplexity / Google SGE / Claude (cited vs mentioned vs absent)
- GEO citation MEASUREMENT (the tracked-numbers layer): run a fixed prompt panel (30-100 bucketed buyer queries) and report citation rate + mention rate + citation share + share-of-voice per engine + blended, with answer-vs-citation sentiment and the cited source URL (see `elite-technical-geo-2026.md`). The rubric below scores the page (cause); the panel measures citations (effect)
- Score the property against the **GEO audit rubric** in `aeo-ai-visibility.md` (100-pt weighted: robots.txt AI-bot access, llms.txt depth, JSON-LD richness, brand/entity coherence, content structure, freshness, AI-discovery endpoints) - this replaces the old "no perfect tool yet" hand-wave with a scored, repeatable number
- Citability score (the 47-method content-quality lever; prioritize Cite-Sources / Quotation / Statistics / Fluency)
- Schema markup AI-relevance audit (Organization, Person, Product, FAQPage)
- Author + org authorship signals
- llms.txt presence / coverage
- Bonus flags: CDN edge bot-blocking, JS-only rendering, negative signals, prompt-injection patterns

## Phase 6 - SaaS Health Report (the deliverable)
**Structure:**
1. **Metrics at a Glance** - table of CWV scores, ranking distribution, backlink profile
2. **Overall Picture** - 2-3 paragraph narrative
3. **Priority Issues (cap at 3)** - biggest leverage fixes
4. **What's Working** - preserve the wins
5. **90-Day Focus** - single metric to move + the plays to move it

Single-page summary first, full appendix after.
