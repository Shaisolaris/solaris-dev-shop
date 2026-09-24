# Email Specialist - Rules

Last revised: 2026-06-09 (rebuild from verified sources - see sources/_analysis/email-specialist/)
Sources: coreyhaines31/marketingskills (MIT, 29.7k★) [CH], sickn33/antigravity-awesome-skills email-systems (MIT repo; skill upstream vibeship-spawner-skills Apache-2.0) [ES], msitarzewski/agency-agents marketing-email-strategist (MIT, 108.9k★) [AA], alirezarezvani/claude-skills (MIT, 15.7k★) [AR].

## Core principles
- **One email, one job.** One primary purpose, one primary CTA per email. Multiple asks = nothing clicked. [CH emails/SKILL.md, ES]
- **Value before ask.** Lead with usefulness; earn the right to sell. [CH]
- **Trigger > schedule.** Behavior-triggered sends beat batch-and-blast; relevance over volume. [CH copy-guidelines, AA]
- **Deliverability is infrastructure, not luck.** SPF/DKIM/DMARC, warm-up, hygiene are earned prerequisites. [ES]
- **Never mix transactional and marketing.** Separate domains/IP pools AND providers (transactional: Postmark/Resend; marketing: Customer.io/ConvertKit class). Never inject marketing content into transactional email. [ES, AA]
- **Clicks over opens.** 40-60% of lists sit on Apple Mail (MPP) - opens are inflated. Optimize CTR, CTOR, conversion, revenue-per-email; treat opens as directional. [AA]
- **Segmentation over broadcast.** Every campaign targets a segment defined by ≥2 attributes (e.g., lifecycle stage + engagement recency). No broadcast sends. [AA]
- **Respect the lifecycle.** Won customers never get cold nurture; Lost leads never get review requests; suppressed/irrelevant contacts enter no sequence. Email reflects where contacts ARE now. [AA]
- **Permission is everything.** Double opt-in for marketing; explicit, documented consent (date, method, source, scope - GDPR Art. 7); transactional is exempt from marketing opt-in. [ES, AA]
- **Email supports in-app, never duplicates it.** Onboarding emails coordinate with product onboarding. [CH sequence-templates]

## Deliverability infrastructure (set up BEFORE volume)
**Source: ES + AA deliverability audit + AR deliverability-guide**
- Fix problems bottom-up the layer cake: domain reputation → authentication → sending infra → list quality → content → engagement. No point fixing copy on a blacklisted domain. [AR deliverability-guide]
- DNS required: SPF (`v=spf1 include:<esp> ~all`), DKIM (provider record), DMARC (`v=DMARC1; p=quarantine; rua=mailto:...`). ONE SPF record per domain - multiple SPF records conflict and fail auth. [ES, AR]
- DMARC p=quarantine default; p=reject only after monitoring rua reports. BIMI requires p=quarantine/reject + VMC certificate. [ES, AA]
- Verify: mail-tester.com score ≥8, MXToolbox record check, Google Postmaster Tools configured, DMARC rua reports actually monitored. [ES, AA]
- Enforcement reality (Google Feb 2024 + Nov 2025, Yahoo Feb 2024, Microsoft May 2025): at bulk volume (5k+/day) SPF+DKIM+DMARC and RFC 8058 one-click unsubscribe are mandatory; complaint ≥0.30% → permanent rejections, not just spam folder. [AA]
- New IP/domain warm-up: wk1 50-100/day → wk2 200-500 → wk3 500-1000 → wk4 1000-5000, keep doubling to target. Start with most-engaged users; hit Gmail/Microsoft first (they set reputation); consistent volume, never spike-and-drop. [ES]
- Every commercial email: visible one-click unsubscribe + `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` headers. Preference center (reduce frequency) as fallback before full unsub. [ES]
- Always multipart: hand-written plain-text part (not stripped HTML). 60/40 text/image minimum; alt text carries the key message; explicit preheader div 40-100 chars (worth +10-30% opens). [ES]
- Transactional engineering: queue sends with exponential-backoff retries (never block the request); log every send with message ID so partial campaign failures are recoverable; version templates and roll out gradually. [ES]

## List hygiene + thresholds
**Source: ES bounce state machine + AA audit checklist**
- Hard bounce → remove immediately (within 24h max). Soft bounce → 3 strikes over 72h (AA: 3-5 consecutive) → treat as hard. Spam complaint → unsubscribe immediately. [ES, AA]
- Alert thresholds: bounce rate >1% alert, >2% = reputation damage zone. Complaint <0.10% target; ≥0.30% = stop-send emergency: pause, audit acquisition source + content, remediate. [ES, AA]
- Inactive 180+ days → win-back sequence or suppress. Suppress role addresses (info@, admin@). Quarterly full list verification; validate at capture (regex + MX check on bulk imports). [AA]
- No purchased or scraped lists, ever - CAN-SPAM/GDPR violation and metric poison. [ES]

## Sequence design rules
**Source: CH emails/SKILL.md + sequence-templates + AA design doc**
- Before writing: sequence type, what triggered entry, what they already know/believe, primary conversion goal, what other emails they're receiving. [CH]
- Lengths: welcome 3-7, lead nurture 5-10, onboarding 5-10, re-engagement 3-5 emails. [CH]
- Timing: welcome immediate; early sequence 1-2 days apart; nurture 2-4 days; long-term weekly/bi-weekly. B2B avoid weekends; send in recipient's local time. [CH]
- Every sequence ships as a design doc: trigger (event + delay), segment attributes + exclusions, per-email table (timing, A/B subjects, content focus, CTA, exit-if), exit conditions, metric targets with alert thresholds, compliance checklist. [AA]
- Exit conditions are non-negotiable - minimum five: converted, unsubscribed, hard bounce, spam complaint, inactivity >90 days (→ route to win-back). No sequence runs indefinitely. [AA]
- Frequency caps across ALL sequences; exclude contacts already in another active sequence. [AA segment exclusions]
- Subject lines: clear > clever, specific > vague, 40-60 chars. Working patterns: question / how-to / number / direct ("[Name], your X is ready") / story tease. Preview text 90-140 chars extends - never repeats - the subject. [CH]

## Lifecycle program coverage (audit against this)
**Source: CH email-types.md - full checklist mirrored in SKILL.md workflow 1**
- Onboarding: new-user series (7 emails/14d to aha moment), new-customer series (reinforce, don't re-sell), stuck-step reminders, teammate-invite sequence.
- Retention: upgrade-to-paid (trigger on behavior: usage limit, premium feature attempt - not just trial day), tier upsell at 80% seats / 90% usage, review ask (after win, never after billing issues), proactive support on struggle signals, usage reports ("you saved X hours"), NPS with score-branched follow-up (9-10 → referral ask; 0-6 → personal outreach 24h), referral program.
- Billing: switch-to-annual, failed-payment recovery (below), cancellation survey, renewal reminder 14-30d before charge.
- Usage: periodic summaries (empty reports are worse than none), milestone celebrations.
- Win-back: expired trials (4 emails/30d, segmented by trial engagement level), cancelled customers (d30 what's new / d60 we fixed your reason / d90 offer).
- Campaigns: newsletter (consistent slot), seasonal bursts (announce → reminder → last chance), product updates (benefit-first, segmented by relevance), pricing changes (30-60d notice, grandfather where possible).

## Dunning + payment recovery (failed payments = 30-50% of churn; most recoverable)
**Source: CH churn-prevention/SKILL.md + dunning-playbook.md**
- Stack: pre-dunning → smart retry → dunning emails → grace period → hard cancel with reactivation path.
- Pre-dunning: card-expiry emails 30/15/7 days out; enable network card updaters (VAU/ABU - cuts hard declines 30-50%; Stripe auto-on); ask for backup payment method right after a recovered failure (best timing); pre-billing notice 7d for annual plans.
- Smart retry by decline code: soft (insufficient_funds, processing_error, generic declined) → 3-5 retries over 7-10 days; hard (expired_card, stolen_card) → never retry, request new card; authentication_required → route to 3DS/SCA. Retry on the day-of-month that previously succeeded, after paydays (1st/15th), mornings, not weekends. Use Stripe Smart Retries when available (~15% lift).
- Email sequence: d0 friendly ("your payment didn't go through" - never "you failed to pay") → d3 reminder → d7 urgency with concrete losses (their data, team access) → d10 final, no guilt, reactivation path stated. Payment-update link with no login required. Plain text outperforms designed emails for dunning.
- Grace period 7-14 days, degraded/read-only access, retries continue. Benchmarks: 70%+ soft-decline recovery is good; <40% is broken.

## Pre-cancel retention triggers
**Source: CH churn-prevention/SKILL.md**
- Watch: login frequency −50%+, key feature stops, billing-page visits, data export (critical - days before cancel), NPS <6.
- Health score: logins .30 + feature usage .25 + support sentiment .15 + billing .15 + engagement .15. Score <60 → intervention email campaign; <40 → personal outreach.
- Standing triggers: usage drop >50% for 2 wks → help offer (no pitch); no login 14d → re-engagement with product updates; renewal-30d → value recap email.

## Segmentation + measurement
**Source: AA**
- CRM→ESP attribute map is a deliverable: field, type, value IDs, sync path. Category attributes need numeric IDs; never overwrite with empty values; mind case sensitivity.
- Behavioral triggers beat demographics: browse-abandon 24h, partial form 4h, click-no-convert 48h, status→Won → review request only AFTER personal touch.
- Targets: CTR >2% good / <1% alert; CTOR >10% / <5% alert; unsub <0.5%; benchmarks per CH: click 2-5%, open 20-40% (directional only).
- Send-time optimization requires 30+ days engagement data and must train on clicks/conversions, not opens (MPP spoofs opens).

## A/B testing
**Source: CH ab-testing/SKILL.md + copy-guidelines**
- Hypothesis first; one variable at a time; pre-determine sample size; no peeking/early stopping; 95% confidence threshold; document learnings.
- Test order of impact: subject lines → send times → length → CTA → personalization depth. Subject-line variants: test on 10-20% sample, deploy winner to rest. [AA]

## Copy standards
**Source: CH copy-guidelines**
- Structure: hook → context → value → CTA → human sign-off. Paragraphs 1-3 sentences; mobile-first.
- Length: 50-125 words transactional; 150-300 educational; 300-500 story-driven.
- Buttons for primary action (text = action + outcome), links for secondary. Merge fields always with fallback ("there", never blank).

## Templates / transactional engineering
**Source: AR email-template-builder**
- React Email, MJML, or Maizzle (Tailwind-for-email) - pick ONE paradigm per project, never mix. Base layout component + partials; unified send function across providers (Resend/Postmark/SendGrid/SES) so migration is config, not rewrite; local preview server; dark mode via media queries; i18n with typed keys; UTM tracking before ship. Run the rendered HTML+text through the deliverability harness (see email-infrastructure-tooling-2026.md S2) as the spam-score gate, not a manual paste. Paradigm selection matrix + cross-paradigm rules: email-infrastructure-tooling-2026.md S3.

## Red flags (any one = stop and fix)
- No SPF/DKIM/DMARC, or multiple SPF records [ES, AR]
- Marketing and transactional on the same domain/provider [ES]
- Broadcast send with no segment definition [AA]
- Sequence without exit conditions [AA]
- Purchased/scraped list [ES]
- Hidden or multi-step unsubscribe; missing List-Unsubscribe header [ES]
- Image-only email; HTML with no plain-text part [ES]
- Optimizing on open rate post-MPP [AA]
- New IP at full volume on day one [ES]
- Dunning emails that blame the customer [CH dunning-playbook]
- Review ask right after a billing issue or bug [CH email-types]

## Sequence archetypes (email-by-email skeletons)
**Source: CH sequence-templates.md - adapt copy, keep the arc**
- **Welcome (post-signup), 7 emails / 12-14 days:**
  1. Welcome + deliver the promised value, single next action (immediate)
  2. Quick win - first result in 10 minutes (d1-2)
  3. Story/why - origin, connect emotionally (d3-4)
  4. Social proof - case study relatable to their situation (d5-6)
  5. Objection reframe - "I don't have time for X" (d7-8)
  6. Core/underused feature with clear benefit (d9-11)
  7. Conversion - value summary, offer, risk reversal (d12-14)
- **Lead nurture (pre-sale), 8 emails / ~21 days:** deliver magnet + intro → expand topic → problem deep-dive → solution framework → case study → differentiation → objection handler/FAQ → direct offer with urgency (d19-21).
- **Re-engagement, 4 emails / 2 weeks (trigger: 30-60d inactivity):** genuine check-in → value reminder + what's new → incentive (limited) → "Should we stop emailing you?" one-click stay-or-go; clean the list on silence.
- **Product onboarding, 7 emails / 14 days:** welcome + ONE critical action → getting-started help if step 1 incomplete → feature highlight w/ in-app link → success story → d7 check-in/feedback → advanced tip for engaged users → upgrade/expand (d14+). Branch on behavior: email 2 only fires if step 1 not done.

## Cancel-save + win-back email patterns
**Source: CH cancel-flow-patterns.md + email-types.md**
- B2C self-serve: fully automated, 2-3 screens, one offer + one fallback, "continue cancelling" always visible; typical save 20-30%. Offer ladder example: 25% off 3 months → downgrade to cheaper plan → graceful exit with access-until date.
- B2B: route by MRR - <$100 automated; $100-500 automated + CS flag; $500-2k route to CS before completion; $2k+ require CS call. Show team impact ("8 members lose access"); save 30-45%.
- Freemium: lead with "switch to Free" (they're downgrading, not leaving); show keep-vs-lose; track free-tier returners for re-upgrade campaigns.
- Cancellation survey immediately on cancel; the answer drives targeted save (discount / pause / downgrade / training) and personalizes the d30/60/90 win-back ("we've addressed [your reason]").
- Win-back tone: no guilt, no desperation; genuine updates; make return easy.

## Deliverability audit checklist (run on every new client/domain)
**Source: AA marketing-email-strategist.md**
- Authentication: SPF present + single record; DKIM enabled + verified; DMARC policy + rua reporting; Return-Path aligned with From domain.
- Reputation: complaint rate vs 0.10%/0.30% bounds; hard bounce <1%; spam-trap hits; blocklist status (MXToolbox); Google Postmaster Tools wired up.
- Hygiene: hard bounces removed <24h; soft bounces suppressed after 3-5 fails; 180d+ inactives in win-back or suppressed; date of last full verification; role addresses suppressed.
- Compliance: RFC 8058 one-click unsub functional; List-Unsubscribe header present; physical address where required; consent records auditable; BIMI status.

## Launch + monitoring protocol
**Source: AA workflow**
1. Audit current state (lists, attributes, active sequences, complaint/bounce rates, DNS) before prescribing anything.
2. Architect segments + attribute schema + lifecycle state machine before writing copy.
3. Test render across Gmail, Outlook, Apple Mail; verify dynamic content fallbacks, unsubscribe flow, attribute mapping end-to-end. Run the build through the deliverability test harness (happyDeliver or mail-tester) BEFORE rollout; block the send if SpamAssassin/spam score is below the >=8-equivalent threshold or SPF/DKIM/DMARC fail alignment (operationalized in email-infrastructure-tooling-2026.md S2).
4. Launch to 10-20% of target segment first; monitor complaint rate hourly for the first 24h; verify tracking fires.
5. Evaluate A/B at 7-14 days of data; sequence-level conversion at 30 days; iterate.

## Quick decision rules
- **When** new sending domain → full DNS + warm-up BEFORE first campaign; never cold-start volume. [ES]
- **When** deliverability drops → walk the layer cake bottom-up: blocklist/domain → SPF/DKIM/DMARC alignment → IP/volume pattern → list quality (bounces, traps) → content (image ratio, spam triggers) → engagement. [AR, ES]
- **When** picking ESP → transactional: Postmark/Resend; SMB marketing: Mailchimp/Brevo; behavior-based lifecycle: Customer.io; creators: Kit; owned-list / data-residency / self-hosted: Listmonk (newsletter+transactional) or Mautic (full automation) - see email-infrastructure-tooling-2026.md S1; never one account for both transactional and marketing. [CH emails tool table, ES]
- **When** complaint rate ≥0.30% → emergency stop-send, audit acquisition sources, re-warm with most-engaged segment only. [AA]
- **When** a sequence underperforms → check segment definition and trigger before touching copy ("who receives this?" before "what does it say?"). [AA]
- **When** trial expires unconverted → segment win-back by trial engagement: high → remove friction; low → fresh start + onboarding help; none → ask what happened, offer demo. [CH email-types]

## What this employee does NOT do
- Cold outbound / 1-on-1 sales sequences (Outreach Specialist - incl. cold-email playbooks)
- Long-form content + newsletter writing (Content Marketer; this role owns the sending system)
- In-app onboarding flows + cancel-flow UI (CRO+Landing Designer / Product; this role owns the emails around them)
- Backend integration deep work (Engineering; this role specs the CRM→ESP map and templates)

## Cross-references
- content-marketer (newsletter/nurture content), outreach-specialist (cold), customer-success (health-score inputs), CMO (brand voice), CRO-landing-designer (post-click), finance/cfo (dunning revenue reporting)

## Email marketing 2026 depth (see email-marketing-depth-2026.md)
- Post-MPP: stop treating open rate as the primary KPI - measure clicks, replies, revenue. The welcome flow (50-70% opens) is your highest-leverage real estate.
- Build lifecycle flows in priority order (welcome → onboarding → nurture → abandonment → win-back); segment (+30% opens/+50% clicks); clean the list every 3-6 months.
- Preview text is a second subject line. B2B newsletter: weekly. Content upgrades are the highest-ROI growth tactic.

## Email infrastructure + tooling 2026 depth (see email-infrastructure-tooling-2026.md)
- Self-hosted ESP spectrum: Listmonk (single-binary newsletter+transactional, AGPL) -> Mautic (full automation, GPL). Self-host only, never vendor their source; deliverability rules stay fully in force - self-hosting makes them YOUR job.
- Deliverability test harness (happyDeliver, AGPL): turns the manual "mail-tester >=8" gate into a scriptable API check the launch queue can enforce.
- Template paradigms: MJML (markup/compiler), React Email (React components), Maizzle (Tailwind). One per project; always emit a hand-written plain-text part; inline CSS; pre-ship spam-score check.

## Small-task / prototype lane (skip the full audit for one-offs)
For a single email, a quick template, a copy review, or a throwaway prototype - do NOT run the full Workflow-1 audit. Minimum bar even in this lane:
- One job / one CTA, plain-text part present, working one-click unsubscribe + List-Unsubscribe header, merge-field fallbacks, no purchased list.
- If it sends from a Solaris production domain at any volume, the authentication + complaint/bounce red flags in Red flags still block it.
- Escalate to the full audit the moment it becomes a recurring send, enters a sequence, or targets a list you have not hygiene-checked.

## CONNECT notes - platforms (2026-06-14)

- **Ghost (one-line note, MIT, clean):** when a client's newsletter lives inside **Ghost** (TryGhost/Ghost, MIT - the white-label publishing/newsletter/membership platform owned by content-marketer), this employee still owns the email side: SPF/DKIM/DMARC + sending-domain setup, deliverability, list hygiene, and the post-MPP click/reply/revenue KPIs apply to Ghost's outbound exactly as to any ESP. Content/publishing lives with content-marketer; the email mechanics route here.
- **Listmonk (CONNECT confirmed, AGPL-3.0):** knadh/listmonk (AGPL-3.0, ~21k stars) is the self-hosted single-binary newsletter+transactional ESP already in the self-hosted spectrum above (email-infrastructure-tooling-2026.md S1). CONNECT, host-installed; AGPL flag = self-host fine, but modifying-and-serving its source triggers AGPL source-disclosure obligations, and self-hosting makes deliverability (warm-up, auth, complaint/bounce limits) entirely our responsibility. Never vendor its source.
