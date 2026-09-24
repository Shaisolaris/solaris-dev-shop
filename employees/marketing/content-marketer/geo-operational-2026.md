# GEO operational layer - audit, access, citability (2026) - reference

METHODOLOGY absorption (2026-06-13, web research). This file is the OPERATIONAL companion to content-strategy-taste-2026.md: that file says what to write and the GEO content principles; this file says how to make a site machine-citable and how to measure it. No code is bundled. Where the source tool is copyleft or unlicensed, only the methodology is recorded plus a self-host note.

Sources (methodology only): Auriti-Labs/geo-optimizer-skill (MIT) - operational GEO audit model + scoring + citability methods + monitoring; mascanho/RustySEO (GPL-3.0, methodology + self-host note) - crawl/log/CWV diagnostics; amplifying-ai/awesome-generative-engine-optimization (NOASSERTION, cite-only) - GEO field map; underlying research: Princeton "GEO" KDD 2024 (arXiv:2311.09735), AutoGEO ICLR 2026 (arXiv:2510.11438), C-SEO Bench 2025 (arXiv:2506.11097).

## 0. The one-line frame
GEO is not SEO. SEO asks "do you rank?" GEO asks "can an AI answer engine crawl, parse, understand, cite, and be monitored citing your content?" A page can rank #1 on Google and be invisible to ChatGPT/Perplexity/Gemini. The research consensus (C-SEO Bench): content-prose tricks are mostly ineffective; technical INFRASTRUCTURE is what moves citation. Optimize the access + structure layer first, then the prose.

## 1. The four-stage model (use as the audit spine)
1. **Crawled** - can AI bots reach the page? (robots.txt, CDN/WAF rules, server response, JS-rendering dependency)
2. **Understood** - can they parse it? (JSON-LD schema, llms.txt, heading hierarchy, front-loaded answers)
3. **Cited** - is it worth quoting? (citability signals: sources, stats, quotes, fluency, factual density)
4. **Monitored** - are you tracking whether AI engines actually cite you over time? (snapshots + regression, not a one-shot)

Run every GEO engagement through these four in order. Most "we're invisible to AI" problems die at stage 1 or 2 (a blocked bot or thin schema), never reaching the prose.

## 2. Access layer (stage 1 - the part content marketers forget)
- **robots.txt AI-bot allow-list.** ~27 known AI user-agents across three tiers - training (GPTBot, ClaudeBot, Google-Extended), search/citation (OAI-SearchBot, PerplexityBot, ClaudeBot for search), and user-fetch agents. Citation bots must be EXPLICITLY allowed. A blanket disallow makes you uncitable.
- **CDN / WAF gotcha.** Cloudflare / Akamai / Vercel bot-fight modes silently 403 GPTBot/ClaudeBot/PerplexityBot even when robots.txt allows them. Check at the edge, not just the file.
- **llms.txt.** A root /llms.txt (plus optional /llms-full.txt) that maps your key pages for LLMs - needs an H1, a blockquote summary, sectioned links, real depth. Treat it like a sitemap written for models.
- **AI-discovery endpoints (emerging).** /.well-known/ai.txt, /ai/summary.json, /ai/faq.json - low-cost, forward-looking signals.
- **JS-rendering.** If content only exists after client-side JS, many bots see an empty shell. Server-render or pre-render the substance.
- **Crawler EVIDENCE.** The honest measure of stage 1 is your server logs: filter Apache/Nginx access logs by AI user-agent to see who actually fetched you and how often. (Tooling: RustySEO log analyser - GPL-3.0, self-host; or parse logs directly. Do not vendor its code.)

## 3. Understood + cited (stages 2-3 - the citability rubric)
A practical scoring rubric distilled from the geo-optimizer audit model. Use as a per-page checklist; weights are relative priority, not gospel.

| Area | Weight | Looks for |
|------|:--:|---|
| robots.txt AI access | 18 | Citation bots explicitly allowed across the 3 tiers |
| llms.txt | 18 | Present, H1 + summary blockquote, sectioned, deep, companion full file |
| Schema JSON-LD | 16 | WebSite, Organization, Article, FAQPage; rich (5+ attributes each) |
| Meta tags | 14 | Title, description, canonical, full Open Graph |
| Content structure | 12 | Single H1, statistics, external citations, clean heading hierarchy, lists/tables, answer FRONT-LOADED |
| Brand + entity | 10 | Brand-name coherence, Knowledge-Graph links (Wikipedia / Wikidata / LinkedIn / Crunchbase), about page, topic authority |
| Freshness signals | 6 | html lang, RSS/Atom feed, dateModified recency |
| AI-discovery | 6 | .well-known/ai.txt, /ai/*.json endpoints |

Score bands (rough): 86-100 excellent, 68-85 good, 36-67 foundation, 0-35 critical.

### Citability methods that actually move the needle (KDD 2024, measured)
Add these to the prose AFTER access is fixed - they are the proven content levers:
- **Cite sources** (+115%) - link the claim to an authoritative source.
- **Quotation** (+41%) - quote an expert/primary source verbatim.
- **Statistics** (+40%) - replace "many" with the number.
- **Fluency** (+29%) - clean, declarative, plain prose; AI engines prefer it.
This is WHY the taste file's "specificity = quality" rule also wins in AI search: the same specific, sourced, stat-backed writing is what gets lifted into AI answers.

### Anti-citation / negative signals (kill these)
CTA overload, intrusive popups, thin content, keyword stuffing, missing author/byline, high boilerplate-to-content ratio. They suppress citation even when access is perfect. (And never use prompt-injection / hidden-text tricks - detectable, and a trust/repute risk.)

## 4. RAG-chunk readiness (why structure beats length)
AI engines retrieve CHUNKS, not pages. Structure so each section is independently liftable: meaningful section word counts, definition-style openings ("X is ..."), clear heading boundaries, and an anchor sentence per section that states the takeaway. One idea per section, front-loaded - the same discipline as one-idea-per-asset, applied within the page.

## 5. Monitored (stage 4 - the loop most teams skip)
- **Snapshot, don't guess.** Periodically capture how target AI engines answer your priority queries and whether you/competitors are cited. A single check is noise; the trend is the signal.
- **Regression-gate it.** Treat GEO score like a test: save history, alert when a deploy drops you below a threshold (e.g. a schema change that breaks FAQPage). The geo-optimizer CLI is MIT and exposes JSON / SARIF / JUnit output + a GitHub Action - if Shai wires CI, pin the action to a commit SHA, not a floating tag.
- **Measure citation presence, not volume.** Per-platform citation profile (ChatGPT vs Perplexity vs Google AI) + share-of-citation vs competitors > raw mentions. Honest caveat: crawler-log evidence proves you were FETCHED, not CITED - keep the two metrics separate.
- **Content decay.** Flag temporal/statistical/version/price decay; evergreen pages need a dated refresh or they stale out of answers (ties to the existing content-decay gotcha in rules.md).

## 6. Where this sits in the workflow + handoffs
- Content marketer OWNS: front-loaded answers, stats/sources/quotes, FAQ blocks, comparison tables, llms.txt content, decay refresh, the citability prose levers.
- Hand to SEO/ASO specialist: robots.txt edits, CDN bot rules, JSON-LD implementation (tool: spatie/schema-org, MIT - fluent JSON-LD builder), CWV, log access. SEO defines target + technical access; content writes the citable substance; SEO QAs on-page.
- Self-host note (licenses): RustySEO is GPL-3.0 and the awesome-GEO list is unlicensed - use their METHODOLOGY, run the tools yourself if useful, do not vendor or copy their code/text into Solaris artifacts. geo-optimizer-skill and spatie/schema-org are MIT and safe to integrate/connect.

## Sources
github.com/Auriti-Labs/geo-optimizer-skill (MIT), github.com/mascanho/RustySEO (GPL-3.0, self-host), github.com/amplifying-ai/awesome-generative-engine-optimization (NOASSERTION, cite-only), github.com/spatie/schema-org (MIT); research: arXiv:2311.09735 (KDD 2024), arXiv:2510.11438 (ICLR 2026), arXiv:2506.11097 (C-SEO Bench 2025).
