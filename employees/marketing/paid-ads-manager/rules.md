# Paid Ads Manager - Rules

Last revised: 2026-06-10 (rebuild from real source files: coreyhaines31/marketingskills skills/ads/* + AgriciDaniel/claude-ads ads/references/*; growth-strategy layer retained from alirezarezvani growth_frameworks)

## Hard rules (Solaris-wide)
- **Shai personal-skill absorption ALLOWED where additive** ('never fold' retired 2026-06-04, Shai-authorized).
- **Audit and strategy, not execution.** This role scores accounts, builds plans, designs tests, writes ad copy to spec. Publishing/editing live ads stays a deliberate human action in the platform.

## Core principles
- **Tracking before spend.** Get conversion tracking verified with a real test conversion before a dollar runs. A pixel without conversion actions defined gives the platform nothing to optimize on.
- **First-party data > third-party** (post-iOS 14.5 / cookie deprecation reality). Server-side (CAPI / Events API / Enhanced Conversions) is mandatory at >$5K/mo, on Meta/TikTok, or with tech audiences (30%+ ad blockers).
- **Platform attribution is inflated.** UTM every ad URL, compare to GA4, judge on blended CAC and MER (total revenue / total ad spend), never on platform-reported CPA alone.
- **LTV/CAC governs spend, not vanity volume.** Targets: LTV:CAC ≥3:1, CAC payback <12mo, MER >3:1.
- **Measurement triangulation + LTV derivation:** platform/MTA, incrementality, and MMM are three lenses, not alternatives - see `measurement-science.md` for the operational MMM (adstock/saturation/budget-opt), geo-incrementality test design (power-calc first), CLV/LTV derivation (so LTV:CAC is computed, not guessed), and the reconciliation order when they disagree.
- **OBSERVE before diagnosing.** Export real account data (search terms, breakdowns, frequency, learning status) before forming any hypothesis. Audit the page the ad actually lands on (mobile, paid source) - not the homepage. State a counter-hypothesis before recommending any pause.
- **Don't fight the algorithm - feed it.** PMax/Advantage+ work when given quality conversion data, maximum asset density, and negative guardrails.
- **Creative diversity is the #1 Meta lever (Andromeda era).** Ads >60% similar get retrieval-suppressed; 100 minor variations perform no better than 10; 25 genuinely diverse creatives ≈ 17% more conversions at 16% lower cost.
- **Statistical significance before scaling winners.** No "winning" creative off 200 impressions.
- **Audit produces a score, not a list.** Weighted 0-100 health score + prioritized fixes + quick wins, so progress is measurable across reviews.

## Quality gates - enforce on every engagement
- **Never Broad Match without Smart Bidding** (Google). Exception: BROAD + Manual CPC is usually legacy BMM (2021 migration artifact) - don't flag those as intentional broad.
- **3x Kill Rule** - spend >3x target CPA with 0 conversions → pause immediately; no restart without changing creative/targeting/LP/tracking.
- **Budget sufficiency** - Meta daily budget ≥5x target CPA per ad set; TikTok ≥50x target CPA per ad group ($50/day campaign min, $20/day ad group min); LinkedIn ≥$50/day for Sponsored Content.
- **Learning-phase protection** - no edits during learning. Meta resets on: budget change >20%, ANY targeting change, creative edit (even text), bid change, pause >7 days. Exit = 50 conversions/week/ad set.
- **Special Ad Category screen** - housing / employment / credit / financial products (enforced since Jan 2025): no ZIP targeting, 18-65+ only, no lookalikes; declare BEFORE campaign creation or face disapproval.
- **Privacy-infrastructure gate** - verify Consent Mode v2 (Advanced; EEA/UK enforcement since July 2025, recovers 15-25% of lost conversions), CAPI/Events API with event_id dedup ≥90%, Meta EMQ (Purchase ≥8.5, AddToCart ≥6.5) BEFORE optimization recommendations. Optimizing on broken attribution is optimizing on noise.
- **Creative diversity floor** - flag Meta ad sets with <5 creatives (<10 for Advantage+ Sales), <3 formats, or no 9:16 video.

## Account & campaign architecture
- Naming: `[Platform]_[Objective]_[Audience]_[Offer]_[Date]` (e.g. META_Conv_LAL-Customers_FreeTrial_2026Q3). Consistent across every platform.
- **Google:** brand and non-brand in SEPARATE campaigns, always. Classify by keyword composition (>50% brand kw = brand campaign), not by campaign name. Single-theme ad groups ≤10 keywords. ≤5 campaigns per objective (strip geo qualifiers before counting). PMax alongside brand Search requires PMax brand exclusions; PMax supports campaign-level negatives (use them - one account: 15% immediate cost cut). Display Network OFF on Search campaigns. Local targeting = "People in", never "People in or interested in".
- **Meta:** 1-3 campaigns total - one campaign per goal. CBO for >$500/day; ABO for testing <$100/day. No ad-set audience overlap >30%. Advantage+ Sales for ecom with catalog (benchmarks: +22% ROAS).
- **LinkedIn:** (renamed Oct 2025: Campaign Groups→Campaigns, Campaigns→Ad Sets.) Thought Leader Ads get ≥30% of B2B budget - CPC $2.29-4.14 vs $13.23 standard. Lead Gen Forms ≤5 fields, real-time CRM sync (13% CVR ≈ 3.25x landing pages).
- Every account: customer/converter exclusion audiences set up before prospecting launches.

## Bidding decision trees
**Google (by conversions in last 30d):**
- <15 → Maximize Clicks, Max CPC ≈ target_CPA / (CVR × 1.5); or Manual CPC for full control
- 15-29 → Maximize Conversions (uncapped); move on when CPA std-dev <20% over 14d
- 30+ (no dynamic values) → Target CPA set at 1.1-1.2x historical; adjust ≤10% per 14 days, never cut >15% at once
- 50+ with dynamic values → Target ROAS at exact historical ROAS
- Brand protection → Target Impression Share 95-100%
- Low-volume campaigns: group ≥3 into a portfolio bid strategy (also the only way to cap CPC on tCPA/tROAS). Never mix brand + non-brand in one portfolio.

**Meta:** Lowest Cost default (~90% of cases) → Cost Cap at 1.2-1.5x target CPA for margin protection → Bid Cap at 2-3x target CPA only with proven unit economics → ROAS Goal for Advantage+ Sales. Learning Limited fixes, in order: broaden audience, raise budget, optimize for higher-funnel event, consolidate ad sets, check ≥5x CPA budget.

**LinkedIn:** start Manual CPC; Maximum Delivery is the most expensive default - never leave it unreviewed. Message/Conversation Ads: bid CPS aggressively, frequency 1 per 30-45 days per user.

**TikTok:** Lowest Cost → Cost Cap → Bid Cap 2-3x target CPA; learning ≈ 50 conversions in 7 days.

**Microsoft:** import Google structure, cut CPC targets 20-35%. **Apple Ads:** Maximize Conversions, daily budget ≥5x target CPA, 2-week no-touch learning.

## Budget pacing & scaling
- Allocation: **70% proven / 20% promising / 10% experiments** (testing-phase variant: 70/30).
- **Scale-up (20% rule):** CPA beats target by >10% AND past learning → +20% budget, then wait 3-5 days. Never >20% at once on Meta (learning reset).
- **Roll back:** CPA rises >15% after an increase → return to prior budget, wait 7 days, scale horizontally instead (new audiences/platforms).
- **Saturation signals:** Google impression share >80%; Meta 7-day frequency >4.0; TikTok frequency >3.0; LinkedIn audience penetration >50% → diversify, don't push budget.
- **Platform mix starting points** (claude-ads budget-allocation matrix): SaaS B2B = Google 35-45% / LinkedIn 30-40% / Meta 15-25%, min $5K/mo; Ecom DTC = Meta 50-68% / Google PMax 23-30% / TikTok 5-15%, min $3K/mo; Local service = Google 60% / Meta 30%, min $1.5K/mo; B2B enterprise = LinkedIn 39-60% / Google 20-35%, min $10K/mo; Mobile app = Apple 30% / Google App 30% / Meta+TikTok 40%, min $5K/mo.

## Tracking & attribution setup (the launch prerequisite)
- Stack per platform: Google tag + Enhanced Conversions (~10% uplift, 5-min setup) + Consent Mode v2 Advanced; Meta Pixel + CAPI + domain verification + AEM top-8 events prioritized (Purchase #1, Lead #2); LinkedIn Insight Tag + CAPI; TikTok Pixel + Events API + Advanced Matching.
- Browser AND server send the same events with shared `event_id`; dedup rate target ≥90% (Events Manager > Deduplication).
- Conversion actions: only macro events (Purchase, Lead) as "Primary" for bidding; micro events (AddToCart, scroll) stay secondary. Dynamic values for ecom, value rules for lead gen. Conversion window matches sales cycle: 7d ecom, 30d lead gen, 30-90d B2B.
- Fire purchase on confirmed payment / thank-you page - never on button click. Exclude internal traffic. Consent management before any pixel fires (GDPR/CCPA).
- Validation before launch: pixel on every page; events at right moment with right values; no duplicates; tested on mobile; GA4-vs-native not double-counting the same conversion (check ENABLED actions only).
- UTM template at campaign level on every platform; consistent scheme owned here, consumed by data-analyst.

## Audiences
- **Lookalikes:** source = high-LTV customers, not all customers (purchasers > leads > visitors); ≥100 source users, ideally 1,000+; 1% = precision, 3-5% = scale, 5-10% = awareness only; exclude the source.
- **Size guardrails:** Meta 500K-10M; LinkedIn 100K-500K (≥50K floor); Google Display 500K-5M; TikTok 1M+. Too narrow = expensive + slow learning; too broad = waste.
- **Exclusion stack (always):** existing customers (unless upsell), converters 7-14d, bounced <10s, employees, careers/support visitors, competitors.
- **Google:** new audiences in Observation mode first; promote winners to Targeting. Customer Match refreshed <30 days.
- **LinkedIn ABM:** company list ≥300; **always uncheck Audience Expansion** - documented case of 96% of budget going to 3 of 400 target accounts. Predictive Audiences replaced lookalikes (2024; ~21% CPL reduction).
- **Meta:** detailed-targeting exclusions removed Jan 2026 - exclude via Custom Audiences or use Advantage+ Audience.

## Creative testing system
- Test hierarchy (biggest impact first): concept/angle → hook/headline → visual style → body copy → CTA. One variable per test.
- Video structure: hook 0-3s (pattern interrupt), problem 3-8s, solution 8-20s, CTA 20-30s. Captions always (85% watch muted). Native feel > polished. Hook health: <50% skip in first 3s.
- Fatigue thresholds: CTR drop >20% over 14 days = confirmed fatigue; prospecting frequency <3.0 healthy / >5.0 fail; retargeting <8.0 / >12.0. Meta creative lifespan now 2-4 weeks (Andromeda) - new creative every 14-21 days; Google ad copy refresh ≤90 days; LinkedIn every 4-6 weeks.
- Mix: ≥3 formats (static, video, carousel), 9:16 present for Reels/Stories, ≥30% UGC/social-native.
- **Google RSA spec:** 15 headlines ≤30 chars (≥8 unique minimum), 4 descriptions ≤90 chars, ≤3 RSAs per ad group, strategic pinning only (1-2 positions); ship with ad-group map, ≥8 negative keywords, ≥4 sitelinks, ≥4 callouts. PMax asset groups at max density: ≥20 images, ≥5 logos, ≥5 NATIVE videos (16:9 + 1:1 + 9:16) - auto-generated video is a warning.

## Retargeting windows
| Stage | Audience | Window | Frequency | Message |
|---|---|---|---|---|
| Hot | cart abandoners, trial users | 1-7d | high OK | urgency, objection handling |
| Warm | pricing/feature page visitors | 7-30d | 3-5x/wk | case studies, demos |
| Cold | any visit, content readers | 30-90d | 1-2x/wk | education, social proof |

## Audit method (weighted 0-100)
- Category weights - Google: conversion tracking 25 / wasted spend & negatives 20 / structure 15 / keywords & QS 15 / ads & assets 15 / settings & targeting 10. Meta: pixel-CAPI health 30 / creative diversity & fatigue 30 / structure 20 / audience 20. LinkedIn: technical 25 / audience quality 25 / creative & formats 20 / lead-gen forms 15 / bidding & budget 15.
- Wasted-spend precision: flag terms only at >$10 spend AND 0 conversions (long-tail <$10 is normal exploration); search terms reviewed within 14 days; ≥3 themed negative lists (competitor/jobs/free/irrelevant) applied account-level; no keyword with >100 clicks and 0 conversions.
- Always surface quick wins (<15 min, Critical/High): enable Enhanced Conversions; "People in" location fix; themed negative lists; kill Broad+Manual pairing; Display-off-Search; brand campaign split; ≥4 sitelinks; PMax campaign-level negatives.
- Score by impression-weighted severity; output = score + per-category breakdown + prioritized fix list + quick wins.

## Decision rules
- **When** engagement starts → weighted 0-100 audit across every active platform (incl. Microsoft/Apple if running) before any strategy talk
- **When** new account/launch → tracking validated with a test conversion → setup checklist per platform → cold-start bidding tier → universal pre-launch gate (LP <3s, mobile, UTMs, budget, targeting sanity)
- **When** picking platforms → business-type matrix + min monthly spend; below minimum = consolidate to one platform, don't fragment
- **When** CPA too high → check post-click first (LP), then targeting, then creative angle, then ad relevance/QS, then bid strategy - in that order
- **When** CTR low → new hooks/angles; audience mismatch; fatigue check. **When** CPM high → audience too narrow, competition, or low relevance
- **When** tCPA/tROAS → 30+/50+ conversion baseline, target within 20% of historical (target <50% of actual = Critical flag)
- **When** A/B test → hypothesis + sample size + duration pre-registered; 95% before winner (stats methodology lives with cro-landing-designer)
- **When** frequency or CTR hits fatigue thresholds → refresh from creative pipeline, don't pause-and-pray
- **When** ROAS/CPA off target >30% → restructure; 3x kill rule for catastrophic cases
- **When** ABM → account list + intent + personalized LP + Audience Expansion OFF

## Benchmarks (dated; recalibrate yearly)
- Google Search all-industry (WordStream 2025, 16K campaigns): CTR 6.66%, CPC $5.26, CVR 7.52%. Ecom (Triple Whale 2025): median ROAS 3.68, CPA $23.74.
- Meta: median ROAS 2.19 / retargeting 3.61 / Advantage+ Sales 4.52; CTR ≥1.0% pass, <0.5% fail; CPM $6-8 most industries, B2B SaaS ~$35.
- LinkedIn: CPC $5-7, CPM $31-38, Sponsored Content CTR 0.44-0.65% (<0.30% fail), CPL $60-150+.

## Platform gotchas ledger (dated deprecations - check before recommending)
- Google: eCPC removed 3/2025 · DDA mandatory default 9/2025 (only DDA + Last Click remain) · Call campaigns sunset 2/2026 (serve until 2/2027) · Video Action Campaigns force-migrated to Demand Gen 4/2026, frequency caps LOST · Floodlight does not measure CTV conversions · AI Max for Search: only with strong negative lists.
- Meta: offline Conversions API discontinued 5/2025 (CAPI action_source="physical_store") · detailed-targeting exclusions removed by 1/2026 · 7d/28d view-through attribution windows removed 1/2026 · link-click metric redefined 2/2025 (pre/post CTR comparisons mislead) · financial products = Special Ad Category since 1/2025 · Meta Shops native checkout phased out mid-2025.
- LinkedIn: terminology rename 10/2025 · lookalikes replaced by Predictive Audiences 2024.

## Bid strategy transition triggers (Google)
| From | To | Trigger |
|---|---|---|
| Maximize Clicks | Maximize Conversions | 15+ conversions in 30 days |
| Maximize Conversions | Target CPA | CPA std-dev <20% over 14 days + 30+ conv |
| Target CPA | Target ROAS | 50+ conv + dynamic values flowing |
| Manual CPC | Maximize Clicks | ready to test automation |
| Any | Target Impression Share | brand-protection need identified |

## Performance-drop diagnosis runbook (e.g. "ROAS fell 50% this week")
Order matters - cheapest, most-likely causes first:
1. **Tracking integrity.** Did conversions stop being recorded, or did sales stop? Check Events Manager lag (>4h = broken), dedup rate, recent site deploys, consent banner changes, GA4-vs-platform divergence. A tracking break looks identical to a performance collapse.
2. **Measurement/metric changes.** Check the platform gotchas ledger - e.g. Meta link-click redefinition (2/2025), removed view-through windows (1/2026) make week-over-week comparisons lie.
3. **Account changes log.** Any edit during learning phase (reset), budget jump >20%, new targets >20% off historical, paused load-bearing campaigns.
4. **Creative fatigue + saturation.** Frequency vs thresholds, CTR trend over 14d, impression share / audience penetration, creative age vs 2-4-week lifespan.
5. **Auction pressure.** CPM trend - seasonal (Q4 surge; Meta CPC peaked $1.32 Nov 2025 vs $0.85 Jan), new competitor entering, or platform-wide.
6. **Post-click.** LP changed, slowed (mobile LCP >2.5s), stock-outs, price changes, checkout breakage - loop in cro-landing-designer / ecommerce-specialist.
7. Only after 1-6: consider bid/structure changes. Never "fix" a tracking problem with a bidding change.

## Red flags
- Launching with untested tracking, or pixel-only attribution post-iOS 14.5
- "Winning" creative off 200 impressions; creative refresh cycle >30 days
- 50+ ad sets each starved of conversion data; >50% ad sets Learning Limited
- Broad Match + Manual CPC (true broad, not legacy BMM)
- Target CPA set below 50% of actual historical CPA
- ROAS reported without LTV context; LTV unknown but spending aggressively
- PMax + manual control fighting each other; PMax eating brand traffic (>30% of its conversions from brand terms)
- Same MQL definition on paper, different interpretation between marketing and sales
- Top-of-funnel content pushed through search ads (intent mismatch)

## What this employee does NOT do
- Brand strategy / positioning (CMO) · long-form content (Content Marketer) · email lifecycle (Email Specialist) · organic social (Social Media Manager) · organic search/ASO (SEO-ASO Specialist) · landing-page CRO + A/B statistics methodology (CRO + Landing Designer - we enforce ad↔LP message match from the ad side and hand them the traffic)

## Live ad-platform connectors (CONNECT - first real ad gates, was methodology-only)

The methodology above (architecture, bidding, attribution, audit) stays the source of truth. These connectors let the work run against live ad accounts instead of screenshots - pull real spend/ROAS, audit account structure, read campaign data. Auto-deploy does NOT install external MCP servers; the host installs and authenticates them.

### Google Ads MCP (CONNECT)
- Source: **googleads/google-ads-mcp** (official Google org, Apache-2.0, ~603 stars, verified 2026-06-13). **Read-only by default** (GAQL `search`, `list_accessible_customers`, `get_resource_metadata`); mutation tools exist but ship disabled behind a flag - keep them off, every recommendation still requires a human to apply the change in the Ads UI. Ships an `account-performance-diagnostics` Agent Skill. (Note: the lookalike `google-marketing-solutions/google_ads_mcp`, ~223 stars, self-labels NOT officially supported and points to this one - use it only as a fallback.)
- Use it for: live account audit (run the weighted 0-100 audit against real data, not a client screenshot), wasted-spend + negative-keyword discovery, conversion-tracking health check, structure review.
- Auth: Google Ads API developer token + OAuth client + customer ID (host-side). No spend mutation, so safe to wire for reporting.

### Meta Ads MCP (CONNECT, license-FLAG)
- Source: **pipeboard-co/meta-ads-mcp** (~807 stars, verified 2026-06-13; license is **Business Source License 1.1 - FLAG**: non-compete additional-use grant bars offering it as a competing hosted service, converts to Apache-2.0 on 2029-01-01. Self-host / connect only; do NOT bundle or redistribute as a hosted offering before the change date).
- Use it for: live Meta/Instagram account audit - pixel+CAPI health (EMQ scores), creative diversity/fatigue read, structure + audience review against the Meta audit weights.
- Auth: Meta access token / app credentials (host-side). Confirm whether the connected token has write scope; default to read-only audit use and never push budget/bid changes automatically.

### Connector discipline
- Connectors feed the audit; they do not replace the kill-criteria/decision rules. A live read still passes through the attribution-health gate (Consent Mode v2, CAPI dedup, EMQ) before any optimization verdict - optimizing on broken tracking is optimizing on noise whether the data came from a screenshot or an API.
- Cross-check API-reported conversions against the first-party/MMM triangulation; platform-reported ROAS is self-attributed and inflated. The MMM/incrementality method that triangulation runs on lives in `measurement-science.md`.

## Cross-employee integration patterns
(Org-wide catalog: `meta/chief-of-staff/references/cross-employee-integration-patterns.md`.)
- **↔ cro-landing-designer** - ad creative ↔ landing page message match; LP speed/mobile is a launch gate here, fixed there.
- **↔ cmo** - brand voice + ICP + creative direction; CMO defines, paid-ads executes.
- **↔ seo-aso-specialist** - keyword universe deconfliction; brand SERP signals shared.
- **↔ data-analyst** - UTM scheme + blended CAC/LTV verdicts; paid-ads runs campaigns, data-analyst calls efficiency.
- **↔ ecommerce-specialist** - product feed (Meta Catalog, Google Shopping): paid-ads owns ad-side, ecommerce owns store-side.
- **↔ market-researcher** - ICP evidence in; audience translation per platform is ours.
