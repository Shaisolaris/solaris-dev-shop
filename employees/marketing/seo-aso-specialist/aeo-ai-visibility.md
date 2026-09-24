# AI Visibility / Answer Engine Optimization

Optimize content for citation by AI search engines (ChatGPT, Perplexity, Google SGE, Claude, Bing Chat), not just Google's blue-link results.

## Why AEO is now first-class
- AI search behavior is fundamentally extractive: it picks specific facts + statistics + named sources from authoritative pages and cites them.
- Pages that win AI citations don't always rank highest on traditional Google - different signal mix.
- Brand mentioned in AI answer → user trusts you without ever clicking. Zero-click win.

## What AI search optimizes for (vs traditional Google)
| Traditional Google | AI search engines |
|---|---|
| Keyword match | Semantic match + extractive facts |
| PageRank / authority | Author authority + structured data |
| User clicks signal | Citation-worthy clear answers |
| Long-tail patterns | Question-format optimization |

## Concrete optimization patterns
- **Direct-answer paragraphs at the top** - first 2 sentences answer the implied question. AI engines extract from these heavily.
- **Statistics with sources** - "73% of agencies report X (Source: Hubspot 2025)." Cited stats get re-cited by AI.
- **Named expert quotes** - author byline + credentials + expertise schema.
- **FAQ blocks with question-format headings** - "What is X?" / "How does X work?" - direct match for AI queries.
- **Definition + examples + comparison** - the trifecta AI engines love to pull from.
- **Schema markup AI-relevant** - Organization, Person, FAQPage (gov/health restriction noted), Article with author, Product with explicit specs.
- **llms.txt file** - emerging convention, list canonical pages for AI training/citation in `https://yourdomain.com/llms.txt`.
- **Wikipedia-style writing** - neutral, factual, well-structured. Wikipedia is heavily cited; emulate.

## Anti-patterns
- Clickbait headlines optimized for human CTR - AI engines skip them
- Content without citations - AI engines can't verify, deprioritize
- Pure SEO content stuffed with keywords - AI engines smell it and discount
- Walled gardens (login-walled or geoblocked content) - AI engines can't read it, won't cite

## Measurement (manual, no perfect tool yet)
- Run weekly brand-name queries through ChatGPT / Perplexity / SGE / Claude
- Note: cited (mentioned with source link) vs mentioned (named without link) vs absent
- Track top-20 queries the client cares about
- Note WHICH page was cited if you can - feeds back to content strategy

## Tools
- Perplexity AI - best-in-class for citation tracking
- Brave Search - uses LLM ranking, transparent
- LLMrefs (emerging) - paid AI-search ranking tracker
- Manual ChatGPT + Claude.ai queries - still the canonical test

## Cross-reference
Phase 5 of the 6-phase SEO audit. Every audit should include AEO testing now - it's not optional in 2026.

---

## GEO audit rubric (methodology, ABSORBed 2026-06-13)

Methodology distilled from Auriti-Labs/geo-optimizer-skill (MIT, 468 stars, github.com/Auriti-Labs/geo-optimizer-skill), itself grounded in peer-reviewed research: GEO: Generative Engine Optimization (Princeton, KDD 2024), AutoGEO (ICLR 2026), C-SEO Bench (2025). Methodology only - no code bundled. To run it as live tooling, self-host: `pip install geo-optimizer-skill` then `geo audit --url <site>`, or wire the MCP server (`pip install geo-optimizer-skill[mcp]`; `claude mcp add geo-optimizer -- geo-mcp`). The package is MIT so bundling is permitted; we keep it as methodology + self-host note to avoid a hard dependency.

Core research finding to anchor on: **infrastructure beats prose.** C-SEO Bench showed most content manipulation is ineffective; if crawlers cannot find and parse the content, rewriting sentences does nothing. So the audit weights technical reachability and structure over wordsmithing.

### The weighted GEO score (100 pts) - audit a page/site against these
- **Robots.txt AI-bot access (/18)** - are citation-class bots (GPTBot, OAI-SearchBot, ClaudeBot, Claude-User, PerplexityBot, Google-Extended, etc.) across the three tiers (training / search / user) explicitly allowed? A blanket block makes the page invisible to AI answers regardless of quality.
- **llms.txt (/18)** - present at `/llms.txt`, with an H1, a blockquote summary, sections, and real links; companion `llms-full.txt` a bonus. This is the single most under-adopted lever for Solaris properties.
- **Schema JSON-LD richness (/16)** - WebSite, Organization, FAQPage (gov/health rich-result restriction still applies), Article present AND rich (5+ meaningful attributes, not stub markup).
- **Meta tags (/14)** - title, description, canonical, complete Open Graph.
- **Content structure (/12)** - one H1, statistics present, external citations, clean heading hierarchy, lists/tables, front-loaded answers (the direct-answer-first pattern already in this file).
- **Brand + entity coherence (/10)** - consistent brand name + Knowledge-Graph links (Wikipedia / Wikidata / LinkedIn / Crunchbase), about page, topic authority. (Ties directly to the multi-property shared-`@id` / `sameAs` discipline in rules.md.)
- **Freshness signals (/6)** - `<html lang>`, RSS/Atom feed, `dateModified`.
- **AI-discovery endpoints (/6)** - `/.well-known/ai.txt`, `/ai/summary.json`, `/ai/faq.json`, `/ai/service.json`.

Score bands: 86-100 Excellent / 68-85 Good / 36-67 Foundation / 0-35 Critical. Use the band as the headline number in the Phase-5 section of the SaaS Health Report.

### Citability score (separate 0-100, content quality across 47 methods)
The highest-leverage levers from the Princeton study, in order of measured lift: **Cite Sources (+115%)**, Quotation (+41%), Statistics (+40% / +33% depending on study), Fluency (+29%). Practically: add a sourced statistic and a named quotation to a thin page before touching anything else.

### Bonus / informational checks (do not affect the core score, but flag them)
- **CDN crawler access** - Cloudflare / Akamai / Vercel can block GPTBot/ClaudeBot/PerplexityBot at the edge even when robots.txt allows them. Check both layers.
- **JS rendering** - is content present without JS? SPA frameworks can hide everything from AI crawlers.
- **Negative signals (8)** - CTA overload, popups, thin content, keyword stuffing, missing author, high boilerplate ratio. These suppress citation.
- **Prompt-injection / manipulation (8)** - hidden text, invisible Unicode, LLM instructions in comments, monochrome/micro-font text, aria-hidden abuse. Audit for these as a trust + safety check (a client site carrying them, even unintentionally, can be penalized or look adversarial to engines).
- **RAG chunk readiness** - section word counts, definition openings, heading boundaries, anchor sentences - does the content segment cleanly for retrieval?
- **Content-decay prediction** - temporal / statistical / version / event / price decay; an evergreen score feeds the content-freshness refresh cadence.

### How this slots into the existing workflow
- This is the operational backbone of **Phase 5 (AI visibility)** in `seo-audit-6-phase.md` - replace the prior "no perfect tool yet" hand-wave with this scored rubric.
- The GEO score + citability score become the AEO baseline numbers in the baseline-snapshot block of `rules.md`.
- Schema-richness checks here also cover the standalone schema-validation need (so a separate schema-validator dependency is not pinned; for one-off validation use Google Rich Results Test + schema.org validator, or self-host adobe/structured-data-validator, Apache-2.0, for CI).

### Self-host note (license-clean)
geo-optimizer-skill is MIT, so the host MAY install it. Until then this rubric is run by hand against any page. DataForSEO (paid) and GSC (free, first-party) remain the live-data sources in `live-search-data-tooling.md`; GEO Optimizer is additive, focused on the AI-citation layer specifically.
