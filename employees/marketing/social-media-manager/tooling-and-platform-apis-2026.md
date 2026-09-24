# Social tooling + platform APIs (2026) - reference

METHODOLOGY absorption (2026-06-13, web research + GitHub verification). Sources: Postiz (gitroomhq/postiz-app, AGPL-3.0, 30.7k stars), Mixpost (inovector/mixpost, MIT, 3.3k), TryPost (trypostit/trypost, AGPL-3.0, 269), Postproxy 2026 API-rules reference, Socialcrawl "Social Media APIs in 2026". This is the TOOLING + API-REALITY layer; the algorithm/practice layer lives in linkedin-and-social-depth-2026.md. Strategy role: we recommend and operate tools, we do not ship the software - so AGPL sources are methodology-only.

## 1. The publishing-tool landscape (build-vs-buy / self-host)
- A modern stack has three tiers: (a) a SCHEDULER/PUBLISHER (queue, calendar, multi-account fan-out), (b) ANALYTICS (per-post + per-channel pull-back), (c) a unified PUBLISHING API for programmatic/agentic posting. One tool often spans all three.
- **Self-hosted open-source** (own your data, no per-seat fees): Postiz (20+ networks incl. Bluesky/Mastodon/Threads/Reddit/Warpcast; ships an MCP server + public REST API; pairs with n8n/Make/Zapier) and Mixpost (Buffer-alternative; visual calendar, per-platform analytics, post versions/conditions, media library, hashtag groups, dynamic variables, reusable templates, workspaces). TryPost is the agent-native newcomer (built-in MCP server lets Claude/Cursor/ChatGPT schedule, publish, and pull metrics in natural language).
- **Self-host note:** Postiz and TryPost are AGPL-3.0 - fine to self-host and use, but AGPL's network-copyleft means if you fork-and-offer-as-a-service you must publish source. For a brand running its own posting, this is a non-issue. Mixpost Lite is MIT (no copyleft); its Pro tier is a one-time paid license.
- **Decision rule:** self-host (Postiz/Mixpost) when data ownership, cost-at-scale, or custom workflows matter and a technical owner exists; use a managed SaaS (Buffer/Hootsuite/Later/Publer/SocialBee) when the team is non-technical and seat cost is acceptable; reach for a unified publishing API (Postproxy/Ayrshare/Blotato-class) only when you are programmatically posting across 3+ platforms and the per-platform integration/maintenance cost exceeds the API bill.
- **Agentic pattern (2026):** the leading tools now expose MCP servers, so an assistant can schedule/publish/pull-metrics conversationally. When recommending tooling for an AI-operated workflow, prefer one with a real public API + MCP server over a UI-only product.

## 2. The 2026 platform-API operating table (publishing)
All major platforms: OAuth 2.0, and most require app review or partner approval before production publishing. Per-platform caps, limits, and gotchas (the numbers that break calendars):

| Platform | Posts/day cap | Text limit | Token lifetime | Access gate | Watch-out |
|----------|---------------|------------|----------------|-------------|-----------|
| Instagram (Graph) | 100/24h; 200 API calls/hr/account (cut from 5,000 in 2025, -96%) | 2,200 (30 hashtags; 125 before "See More") | 1h short / 60d long | Meta App Review + Business Verification | Business/Creator only; JPEG-only (PNG rejected); 2-step container-then-publish; moov atom must be front-of-file |
| TikTok | ~15/creator (SHARED across all API clients + manual posts) | ~2,200 | 24h access / 365d refresh | TikTok audit (unaudited apps forced PRIVATE) | Video-only, no image/carousel; must query creator-info + show username/avatar pre-post |
| X (Twitter) | Free 500/MONTH (~17/day, total not daily) | 280 (25k premium) | No auto-expiry | Pay-per-use default (Feb 2026: ~$0.01/post, $0.005/read); Basic $200/mo & Pro $5k/mo grandfathered; read is paywalled | v1.1 media endpoints deprecated 2025; chunked INIT/APPEND/FINALIZE upload |
| LinkedIn | Undisclosed | 3,000 | 60d access / 365d refresh (fixed from grant) | LinkedIn Partner Program (Company Page required; weeks-months; reject = new app) | Rate limits hidden by design; Posts API (ugcPosts deprecated); asset-registration upload flow |
| Facebook (Pages) | 25/page/24h | 63,206 (~125 before "See More") | 1h / 60d; page tokens can be non-expiring | Meta App Review | Pages only (no personal); permission renamed publish_pages -> pages_manage_posts |
| YouTube (Data v3) | ~6 video uploads (10,000 units/day; upload = 1,600 units) | title 100 / desc 5,000 / tags 500 | 1h access / long-lived refresh (7d if app in "Testing") | OAuth (API key alone cannot upload); audit for higher quota | Failed calls still burn quota; search = 100 units |
| Threads | 250/24h | 500 (+10k attachment) | 1h / 60d | Meta App Review; IG Professional linked | ONLY 1 hashtag/post (unique); 500-char limit breaks IG-caption cross-post |
| Pinterest (v5) | Undisclosed (Trial daily / Standard per-min) | title 100 / desc 500 | 30d access / 365d refresh | Business account; Standard tier needs approval | Limits change without notice |

## 3. The 2024-2026 API contraction (why this is hard now)
- The free-open-social-data era ended: X killed free read access (Basic now $200/mo), Reddit priced commercial use at $0.24/1k calls with ~30 days notice (Apollo shut down rather than pay ~$20M/yr), Meta gated Instagram behind App Review + Business Verification, TikTok restricted its Research API to non-profit universities only.
- **Cost reality (read access):** YouTube free (10k units/day, no approval) -> Reddit free non-commercial -> X $200/mo minimum for any read-heavy workload -> Instagram free but 4-8 weeks of review -> TikTok no official commercial path.
- **Rate-limit models differ per platform:** X = per-app AND per-user 15-min windows; Instagram = dynamic 4,800 x impressions over rolling 24h (high-traffic accounts get higher caps); Reddit = fixed 10-min window (exposes X-Ratelimit-Remaining header); YouTube = unit-cost ledger not request count. No two feel the same.
- **Two recovery strategies that work everywhere:** (1) exponential backoff with jitter on a 429 - 1s, 2s, 4s, 8s up to a 60s cap, random jitter so workers do not retry in lockstep; (2) quota budgeting - track each platform's remaining limit BEFORE the call so one bursty platform does not starve the others.
- **Legality:** scraping public data does not violate the CFAA (hiQ v. LinkedIn, 9th Cir. 2022) but can still violate platform ToS and be actionable (Meta v. Bright Data, 2024). Safe posture: use OFFICIAL APIs for all write/publish operations and any private/user data; third-party read APIs (which carry the ToS risk themselves) only for public read-at-scale.

## 4. Calendar + analytics methodology (tool-agnostic)
- **Content calendar** is the operational form of the 5-pillar mix + cadence: a visual queue (Mixpost/Postiz model) where each slot carries pillar tag + format + platform-native variant + hook. Plan a week ahead, batch-create, leave engagement time daily (see SKILL batch-creation workflow). Per-platform POST VERSIONS (one idea, re-cut per platform) beat raw cross-post - the calendar should hold variants, not one blob.
- **Analytics pull-back loop:** the publishing tool reports per-post + per-channel metrics; map them to the metrics-that-matter table (engagement rate, save/share, DM conversations - NOT raw followers/impressions). The engagement-rate formula and benchmarks are operationalized in SKILL.md.
- **Repurposing as a pipeline** (not a cross-post): one long-form asset -> platform-native cuts (Shorts/Reels/TikTok) + a written form (blog / LinkedIn / X thread). Tooling automates the FAN-OUT, not the RE-CUT - the re-cut is editorial.

## Self-host / licensing summary
- Postiz (AGPL-3.0) + TryPost (AGPL-3.0): self-host freely for your own brand; AGPL network-copyleft only bites if you resell as a hosted service. Methodology absorbed; no code bundled.
- Mixpost Lite (MIT): no copyleft. Pro is a one-time license.
- Postproxy / Socialcrawl: editorial references, cited for the 2026 API facts; not software we bundle.

## Sources
github.com/gitroomhq/postiz-app (AGPL-3.0, 30.7k stars, pushed 2026-05-24); github.com/inovector/mixpost (MIT, 3.3k, rel 2.6.0 2026-03-16); github.com/trypostit/trypost (AGPL-3.0, 269, pushed 2026-06-13); postproxy.dev (Social Media API Rules, updated 2026-03-05); socialcrawl.dev (Social Media APIs in 2026, updated 2026-06-11). All verified 2026-06-13.
