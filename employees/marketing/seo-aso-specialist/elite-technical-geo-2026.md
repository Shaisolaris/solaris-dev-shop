# Elite Technical SEO + GEO Measurement (2026)

Net-new ELITE methodology absorbed 2026-06-20. This file is the elite/live tier that sits ON TOP of the existing methodology, not a replacement. Gate-0 against what was already held:
- The GEO *page-scoring rubric* (100-pt weighted: robots.txt AI-bot access, llms.txt, JSON-LD richness, etc.) already lives in `aeo-ai-visibility.md`. This file does NOT re-do it.
- Live GSC analytics + DataForSEO + App Store scraping already live in `live-search-data-tooling.md`. This file does NOT re-do them.
- What was MISSING and is added here: (1) a rigorous GEO citation-MEASUREMENT framework (fixed prompt panel + share-of-voice math + answer-sentiment), distinct from scoring a page; (2) server log-file analysis + crawl-budget recovery + the three-way AI-crawler split; (3) entity / topical-authority depth beyond the existing multi-property `@id`/`sameAs` rule.

---

## 1. GEO citation MEASUREMENT (the missing rigor)

The existing AEO measurement was "run weekly brand queries by hand, note cited/mentioned/absent." That is the right instinct but not a measurement system. Elite GEO measurement is panel-based and produces tracked numbers you can put MoM deltas against. (Sourced from the 2026 GEO-measurement literature; arXiv 2604.25707 "Citation Selection to Citation Absorption" + the industry citation-metric frameworks.)

### Fixed prompt panel (the foundation)
- A **fixed prompt panel** is a frozen list of 30-100 prompts, run on a schedule, on the same engines, with the same parsing rules. If the panel drifts, the numbers are meaningless - this is the GEO equivalent of the SEO baseline-snapshot discipline.
- Build the panel from real buyer questions, bucketed: **definitions** ("what is X"), **comparisons** ("X vs Y"), **best-tool lists** ("best X for Y"), **how-to** ("how do I X"), and **branded** ("is X any good"). 30-100 keeps it statistically meaningful without becoming unrunnable.
- Run across the engines the client's buyers actually use: ChatGPT (+ ChatGPT search), Perplexity, Google AI Overviews / AI Mode, Claude, Gemini, Bing Copilot. Record per-engine; they disagree and the disagreement is itself a finding.

### The four core metrics (track each over time, per engine + blended)
- **Citation rate** - % of successful answers on the panel that LINK to a page on the client domain. (The hard signal: a clickable source.)
- **Mention rate** - % of answers that NAME the brand, linked or not. Mention rate runs materially higher than citation rate (assistants name brands more often than they link them), so report both - mention-without-link is still zero-click brand equity.
- **Citation share** - the client's citations as a fraction of TOTAL citations in the answer (6 sources, 1 is yours -> 1/6). This is the per-answer competitive density.
- **Share of voice (SoV)** - (client brand mentions / total brand mentions across the tracked panel) x 100. This is the category-level scoreboard vs named competitors.

### Two more layers that separate elite from adequate
- **Answer sentiment vs citation sentiment (score them separately).** Answer sentiment = how the AI describes the brand in prose (shapes the reader before they click). Citation sentiment = what the AI absorbed from the SOURCE it cited. A positive citation feeding a lukewarm answer means the source material is thin; a negative answer despite a citation means the AI is pulling a critical source - chase down WHICH url it cited and fix or out-rank it.
- **Source-URL attribution.** For every cited answer, log WHICH page was cited. This closes the loop back to content strategy: you learn which page-types earn citations and double down. Without this you are optimizing blind.

### Reporting
- Headline number: **citation rate + SoV**, per engine and blended, with the prior-period delta.
- Always pair a flat blended number with the per-engine breakdown - ChatGPT up while Perplexity collapses reads as "flat" in the blend (same gainer-masks-loser rule as the GSC period-over-period workflow).
- The GEO page-score (from `aeo-ai-visibility.md`) is the *input/cause*; these citation metrics are the *output/effect*. An audit reports both: the rubric explains WHY, the panel measures WHAT.

### Tooling note (CONNECT, host-installed)
- Manual panel runs are the license-clean baseline and remain the canonical test. At scale, dedicated GEO trackers (Profound, Peec, Otterly, Ahrefs Brand Radar, Semrush AI-visibility, etc.) automate panel runs + SoV; treat as paid CONNECTs requiring Shai cost approval, same posture as DataForSEO. Do not pin one as a hard dependency - the panel METHOD is the asset, the tool is swappable.

---

## 2. Server log-file analysis + crawl-budget recovery (net-new technical tier)

The prior methodology named "crawl budget" as a concept and flagged "CDN edge bot-blocking," but had no log-file method. Logs are the ONLY ground truth for what crawlers actually did - GSC, crawl emulators, and rank trackers all model crawler behavior; the server access log records it. (Sourced from the 2026 log-file / crawl-budget references + Cloudflare network data.)

### When it applies (do not over-apply)
- Crawl budget is a real constraint only for **large sites** (~1M+ URLs, weekly change), **medium-large** (~10k+ URLs, daily change), or **any site with a pile of "Discovered - currently not indexed"** in GSC. A 200-page brochure site does not need this. Match effort to scope (the small-task lane still applies).

### The method (tool changes, method does not)
1. **Collect** a representative log window (combined log format: IP, timestamp, request line, status, bytes, referrer, user-agent; IIS W3C carries the same fields).
2. **Verify every bot line by IP - never trust the user-agent.** UA strings are trivially spoofed. Two official methods: reverse-DNS (forward+reverse must BOTH resolve, e.g. to `googlebot.com`) and IP-list cross-check against the operator's published JSON (`openai.com/gptbot.json`, `perplexity.com/perplexitybot.json`, `claude.com/crawling/bots.json`). For ClaudeBot the IP list is the ONLY option - Anthropic publishes no reverse-DNS pattern. Tag each line verified/unverified; do all crawl math on the verified set only. Unverified "Googlebot" traffic is a security finding (scraper / spoofed AI bot), not an SEO data point.
3. **Filter to the crawler class** you are analyzing (see the three-way split below).
4. **Group by template** (product vs faceted vs internal-search vs pagination vs orphan) and ask: what share of crawl landed on URLs you actually want indexed? On big parameter-heavy sites, 30-50% of crawl is routinely wasted on never-indexable URLs - and it is invisible to every tool that is not reading the real log.
5. **Recover** at the correct layer: robots.txt to stop the crawl, a status code (410 over 404 for retired URLs - processed faster) for gone content, canonicals + internal-linking changes to consolidate. NEVER use `noindex` to manage crawl budget - Google still fetches the page to read the directive, so the quota is spent either way.
6. **Re-check the log** weeks later to confirm Googlebot redistributed effort toward priority pages. This confirmation step is the one thing no simulation can give you.

### Status codes that are routinely misread
- **304 Not Modified** = good (budget preserved; content unchanged, body not re-fetched).
- **410 Gone** > 404 for intentionally retired URLs (faster de-indexing).
- **Sustained 503s** are NOT harmless - over days they cause Google to reduce crawl frequency and eventually drop URLs.

### The three-way AI-crawler split (the 2026 robots.txt decision, per bot)
The access log no longer carries one kind of bot. Three functionally distinct classes, three completely different allow/block decisions:
- **Indexation** (Googlebot, Bingbot) - crawl -> index -> rank. Blocking = invisible in search. Almost never block.
- **Training** (GPTBot, ClaudeBot, Google-Extended) - fetch -> model training. Blocking = opt OUT of training. A data-rights decision, NOT a visibility one. Google-Extended is separate from Googlebot - blocking it opts out of Gemini training with zero ranking impact.
- **Retrieval** (OAI-SearchBot, Claude-SearchBot, PerplexityBot) - live fetch -> AI-answer citation. Blocking = invisible in AI search. This is the channel GEO citations come from - blocking it accidentally is a self-inflicted GEO wound.
- Only ~14% of top-10k domains have ANY AI-specific robots.txt rules - most sites are making the training-vs-retrieval call by accident. Make it deliberately, per bot. Note CDN edge rules (Cloudflare/Akamai/Vercel) can block these even when robots.txt allows - check BOTH layers (ties to the existing CDN-bot-blocking flag in the GEO rubric).
- User-triggered fetchers (ChatGPT-User, Perplexity-User) may ignore robots.txt - block at the edge if required.

### Tooling tiers
- Small/occasional: filtered spreadsheet or a parse script, manual IP verification.
- Recurring: Screaming Frog Log File Analyser (auto-verifies bots, surfaces orphans; free to 1k events).
- Enterprise/continuous: Botify or Lumar (millions of events, log+crawl+analytics correlation, template segmentation).

---

## 3. Entity SEO + topical-authority depth (net-new content/E-E-A-T tier)

The prior methodology held the multi-property shared-`@id` / `sameAs` rule and pinned E-E-A-T to the Sept-2025 Quality Rater Guidelines. What was missing is the entity-disambiguation + topical-authority-mapping discipline that 2026 AI-search rewards (Gemini and AI Overviews are trained on the Knowledge Graph, so entity clarity now feeds BOTH classic ranking AND AI citation).

- **Entity establishment + disambiguation.** Make the brand, its people, and its products unambiguously identifiable as entities in Google's Knowledge Graph. Concretely: `Organization`/`Person` schema with `sameAs` to authoritative nodes (Wikipedia, Wikidata, LinkedIn, Crunchbase, official profiles), a consistent canonical name, and an About page that states what the entity IS. This is the "brand + entity coherence /10" line of the GEO rubric, deepened into an explicit workstream rather than a checkbox.
- **Topical authority = entity COVERAGE, not page count.** Engines evaluate the breadth + depth of entity coverage across the whole site, not page-by-page. Build a topic/entity map: the core entity, its sub-entities, and the relationships, then ensure the site covers the cluster comprehensively (pillar + cluster already in SKILL.md - this is the entity-driven way to SCOPE the cluster). Gaps in the entity map are the highest-leverage content briefs.
- **E-E-A-T as entity trust.** The Experience/Expertise/Authority/Trust signals (author schema, credentials, original research, citations) are how an entity earns trust in the graph. Pin judgments to the current QRG edition (already in rules.md); this adds the entity LENS - "does Google know who this author is as an entity, and is that entity linked to authoritative co-citations."
- **How it slots in:** entity/topical-authority work is the strategic spine of Phase 3 (Content) + Phase 5 (AI visibility) in the 6-phase audit. The entity map is built once per engagement and drives both the content calendar and the GEO citation panel (the panel's "definition/comparison" buckets ARE entity queries).

---

## Host-wiring needed for the elite/live tier
- **GSC** (free, first-party) - already documented in `live-search-data-tooling.md`; the source of truth for owned-property crawl stats + indexing.
- **Server log access** - the host/client must provide the raw access logs (Apache/Nginx/IIS) or grant access to the log platform (Cloudflare Logpush, Botify, Lumar). No logs = no log analysis; this is a client-deliverable dependency to flag at scoping.
- **Crawler** - Screaming Frog or Sitebulb (desktop) for the crawl half; Log File Analyser for the log half. Host-installed.
- **GEO citation tracker** (optional, paid CONNECT) - a panel-runner (Profound / Peec / Ahrefs Brand Radar / Semrush) automates the citation panel; manual runs are the license-clean baseline. Cost-approval required, same as DataForSEO.
