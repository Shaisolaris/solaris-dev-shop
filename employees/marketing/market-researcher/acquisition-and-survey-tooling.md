# Acquisition + Survey Tooling (DEEPEN, methodology-only)

Absorbed 2026-06-13. This is the HOW-to-acquire and HOW-to-field layer under methodology this employee already prescribes: Workflow 1 says "scrape & extract" with no engine; the SEO/market-pull and watering-hole steps assume search with no engine; rules.md prescribes Van Westendorp / MaxDiff / Likert with no fielding path. No code is bundled - copyleft/non-OSI sources (Firecrawl AGPL, SearXNG AGPL, LimeSurvey GPL) are absorbed as methodology + self-host note ONLY; the host runs the tool, this repo carries no copied code. Full provenance + verification in TOP5-CANDIDATES.md.

Ethics gate (rules.md hard rule, unchanged): public sources only, obey robots.txt, no pretexting, no scraping behind logins. Every tool below is configured to respect that or it does not run.

## 1. Page acquisition for teardowns (the scrape step in Workflow 1)
Tooling: **Firecrawl** [AGPL-3.0, FLAG - self-host or use the MIT firecrawl-mcp-server; host installs, no code bundled], **Scrapy** [BSD-3, permissive baseline], **crawl4ai** [Apache-2.0, permissive LLM-scrape alternative].

- **Engine choice:** quick scan / handful of public pages -> Firecrawl (page -> clean markdown/JSON in one call) via the MIT firecrawl-mcp-server when the host has wired it. Deep profile across many pages, or when a permissive dependency is required -> Scrapy (full crawl control). crawl4ai is the Apache middle ground for LLM-ready markdown without an AGPL dependency. Pick ONE per engagement; do not mix outputs without normalizing.
- **Polite-crawl contract (non-negotiable, operationalizes the ethical-intelligence rule):** obey robots.txt; set AUTOTHROTTLE / per-domain delay (>= ~1 req/s, back off on 429/503); cap concurrency per domain; identify with a real, contactable User-Agent; never log in or bypass paywalls. Scrapy: `ROBOTSTXT_OBEY=True`, `AUTOTHROTTLE_ENABLED=True`, `CONCURRENT_REQUESTS_PER_DOMAIN` low. Firecrawl: use its crawl depth/limit + respect-robots options.
- **Extract, do not hoard:** per the scrape priority (homepage, pricing, features, about, customers, integrations, changelog) request structured extraction (schema/JSON) for the fields the fixed profile template needs - headline/value-prop/CTA, tiers+prices+billing, founding/team/funding, changelog entries. Markdown for human reading; JSON for the side-by-side table.
- **Persist raw, then synthesize:** write each fetch into `competitor-profiles/raw/<slug>/<YYYY-MM-DD>/scrapes/` BEFORE parsing (rules.md raw-data-persistence contract); never overwrite a prior date's folder. The dated snapshot is what lets the refresh pass diff "what moved" into the Change Log.
- **Change tracking = the refresh loop:** Firecrawl change-tracking (or a diff of two dated snapshots) operationalizes the refresh order (pricing page -> SEO -> changelog) and the standing-intel "messaging/pricing diff" signals. A diff with no dated baseline is not evidence.

## 2. Vendor-neutral search + discovery (SEO/market-pull + watering-hole steps)
Tooling: **SearXNG** [AGPL-3.0, FLAG - self-host; host runs the instance, this repo carries no code].

- Self-hosted meta-search aggregates ~70 engines behind one JSON API - the vendor-neutral SERP layer for "their organic competitors", top-ranked pages, and "go find research" discovery, WITHOUT per-vendor SERP-API keys or per-engine ToS-violating scraping.
- **Discovery, not the verdict:** SearXNG surfaces candidate sources (subreddits, forums, review pages, competitor mentions); it does not rank market size. Every surfaced source still goes through evidence discipline - cited, dated, confidence-labeled. Treat result ordering as a lead, not a finding.
- Pair with the SparkToro line in the monitoring source map: SearXNG finds WHERE the conversation is; the watering-hole map and SparkToro confirm WHERE the ICP actually is. Use both before declaring a channel.
- For Reddit specifically, prefer the Reddit-native path in references/reddit-voc-tooling.md over generic search - semantic subreddit discovery beats keyword SERP for that channel.

## 3. Reddit VOC acquisition - code/self-host path (complements the hosted MCP)
Tooling: **PRAW** [BSD-2, permissive, host installs].

- references/reddit-voc-tooling.md absorbed the HOSTED reddit-research-mcp ("Dialog", no creds needed). PRAW is the FALLBACK when a client cannot use the hosted MCP (data-residency, no external MCP allowed, or custom pulls): register a Reddit script app, OAuth, then pull subreddit/search/comment trees directly.
- Same discipline as the hosted path: evidence-with-receipts (every quote -> post/comment URL + upvotes + awards), three-layer execution (discover -> inspect -> execute), batch then drill into comment trees only on relevant threads. PRAW respects Reddit's rate limit automatically; do not defeat it.
- Same sampling caveat carries: Reddit skews technical/skeptical/strong-opinion; citations make the bias auditable, not absent. Triangulate against G2/Capterra + tickets + interviews before concluding.

## 4. Survey fielding - the instrument layer under the methodology
Tooling: **LimeSurvey** [GPL-2.0+, FLAG - self-host; host runs the instance, no code bundled], **surveyjs/survey-library** [MIT, the in-app/embedded option].

The methodology already lives in rules.md (Van Westendorp, MaxDiff, Likert, <=10 questions, one concept per question, no leading questions, segment before concluding). This is HOW to build and field it without licensing a commercial panel tool.

- **Van Westendorp PSM:** four currency/number questions - too expensive, too cheap, expensive-but-would-consider, bargain (good value). Field as 4 numeric items; analyze by plotting cumulative curves and reading the intersections (PMC / OPP / range of acceptable prices). LimeSurvey numeric question type; randomize nothing in the 4 (order is fixed by definition) but randomize surrounding blocks.
- **MaxDiff (best-worst scaling) for tier packaging:** present balanced subsets of features; respondent picks most + least important per set. LimeSurvey array + choice question types with randomized item order; aim for each item shown 3+ times across sets. Output = utility/importance scores that decide which features gate which tier (Good-Better-Best).
- **Likert + matrix** for attitudes/satisfaction; balanced scales, no double-barreled items, one concept per row.
- **Hygiene the platform enforces:** randomization (item + block order to kill order bias), quotas (hit the segment minimums before the meh-majority bias dominates), branching/skip logic, and response export to CSV for the segment-before-concluding analysis. Disclose sample size and per-channel bias on delivery (rules.md).
- **When NOT to survey:** 5-7 deep interviews beat 50 surveys early (rules.md). Field a survey to VALIDATE a hypothesis interviews discovered, not to discover. Without survey data, deliver the alternatives-anchored pricing recommendation labeled Medium confidence - do not fabricate a curve.
- surveyjs (MIT) is the lighter path when the survey must live inside a client's web app rather than a standalone LimeSurvey instance; same instrument discipline applies.

## CONNECT (host installs - auto-deploy does not install external MCP servers or self-hosted apps)
- **firecrawl-mcp-server** [MIT]: the clean CONNECT path for Firecrawl - host runs the engine, this repo bundles no AGPL code. `agent mcp add` per client; scoped API key (or self-hosted endpoint), never embedded in a repo.
- **SearXNG** [AGPL]: host stands up an instance (Docker); point research at its JSON endpoint. Self-host keeps queries private and avoids per-vendor SERP keys.
- **LimeSurvey** [GPL]: host runs an instance (Docker/managed) for fielding; export CSV for analysis here.
- **PRAW** [BSD-2]: host installs the Python package + registers a Reddit script app; only when the hosted reddit-research-mcp is not usable.

## Fleet doctrine
- **SHA-pin CI:** any survey-export, scrape, or report pipeline shipped through GitHub Actions pins third-party actions to a full 40-char commit SHA, never a floating `@v3` tag (a moved tag is a supply-chain path). Keep the readable tag in a trailing comment; let Renovate/Dependabot bump the SHA. Pin scraper/survey container images to a digest, same principle one layer down.
- **Memory scope keys:** scope acquired research per engagement under `{client}:market-researcher:{project}` - competitor raw-snapshot locations, discovered subreddit/feed sets, survey instrument IDs + field dates, and any panel/quota config. Shared methodology stays global; one client's competitor set, pricing curve, or discovered watering holes never leak into another's defaults.
