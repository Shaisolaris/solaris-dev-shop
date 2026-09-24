# Growth, Sales, and Revenue Operating Standard (2026-07)

Status: active for marketing / sales-outreach / CMO / ecommerce growth loops  
Wave: skill-7fw / skill-wave-growth-revenue-20260724  
Synthetic and professional only. No real prospect or personal data in fixtures.

This standard upgrades research, targeting, experiment, content, and pipeline
quality without violating consent, suppression, deliverability, or platform rules.
External actions remain draft or approval-gated and return receipts when authorized.

## 1. Consent and lawful basis (HARD)

| Channel | Required before send/target | Notes |
|---------|----------------------------|-------|
| Marketing email | explicit opt-in or soft opt-in per jurisdiction + recorded source | honor unsubscribe in all future mail |
| SMS | express written consent (TCPA-class) | stop keywords honored immediately |
| Cold email / LinkedIn | legitimate interest or permission path; no bought lists without verification | suppression always wins |
| Paid ads retargeting | pixel/CAPI consent where required (GDPR/ePrivacy) | no sensitive category targeting abuses |
| CRM enroll | documented basis + purpose limitation | bulk enroll needs approval_preview |

Every draft that proposes contact must include:
- `consent_basis`: opt-in | soft-opt-in | legitimate-interest | contractual | unknown
- `consent_source`: how/when recorded (or UNKNOWN)
- `jurisdiction_notes`: e.g. GDPR, CAN-SPAM, CASL, TCPA relevance

If consent_basis is `unknown`, status is `BLOCKED` for send; draft only.

## 2. Suppression (HARD)

Never propose contact when any of these hit:
- global unsubscribe / suppression list
- complaint (spam report) history
- hard bounce
- legal hold / do-not-contact
- role-based or disposable address when policy forbids
- competitor or employee exclusion lists when provided
- frequency cap exceeded (channel-specific)

Suppression checks are mandatory before any `message_send` approval_preview.
Suppression list wipe or global reactivation requires L2+ human authority.

## 3. Deliverability gates (email and domain)

Before any production send plan:
1. SPF, DKIM, DMARC present and aligned (or listed as blockers).
2. Separate transactional vs marketing streams when volume warrants.
3. Complaint rate target <0.1%; bounce target <2% hard.
4. List hygiene: remove hard bounces, role accounts per policy, inactive per plan.
5. Warm-up required for new domains/IPs; no blast day-one.
6. Post-Apple-MPP: prefer CTR/CTOR/conversion over open rate as primary KPI.

Red flags (block new marketing sends until fixed): missing auth, sudden complaint spike, blocklist hit, purchased list of unknown provenance.

## 4. Platform policy compliance (ads, social, SEO, store)

Drafts must cite current official policy class for the platform in use:
- Meta Advertising Standards / restricted categories
- Google Ads policies / misrepresentation
- LinkedIn Ads and messaging policies
- TikTok / X / YouTube community and ads policies as relevant
- Apple App Store / Google Play ASO rules when claiming ranks or reviews
- Shopify / marketplace policies for store claims and promotions

Prohibited patterns:
- cloaking, fake scarcity without inventory truth
- personal attributes inference for sensitive ad targeting
- review gating that suppresses negative reviews
- SEO doorway pages, pure spun content, link schemes
- scraping competitor private data or CAPTCHA bypass

If policy fit is uncertain: mark `POLICY_REVIEW_REQUIRED` and do not emit Gate: passed for publish/spend paths.

## 5. Experimentation ethics and measurement

- Every A/B or multivariate test names: hypothesis, primary metric, guardrails, sample size or stop rule, duration, and decision owner.
- No peeking-to-win without pre-registered criteria; report sequential testing risk if early stop.
- Holdouts for major lifecycle or pricing tests when revenue impact is material.
- Accessibility and brand voice remain in-bounds for all variants.
- Never run experiments that withhold legally required notices or cancel rights.

## 6. Attribution honesty

- State model used (last-click, data-driven, MTA, media-mix, lift study) and its limits.
- Do not double-count revenue across channels without disclosure.
- Mark modeled or partial conversions as such; never invent ROAS.
- Incrementality claims require test design or clear proxy + confidence.
- Stale benchmarks (>12 months or unknown date) label `STALE`.

## 7. Targeting quality (research to pipeline)

- ICP and segments use observable attributes, not sensitive protected-class proxies.
- Lead lists are synthetic in demos; production lists need source ledger + suppression join.
- Scoring features must be explainable; refuse black-box discrimination patterns.
- Research outputs include source ledger: URL/title/date/what was taken/confidence.

## 8. Approval, receipts, failure, rollback

External mutations stop at approval_preview (see RUNTIME-POLICY.md).

Approval preview shape (mandatory):
```text
APPROVAL_PREVIEW
action: <message_send|spend|mutate_external|...>
target: <system/channel>
payload_summary: <what would happen>
risk: <low|med|high> + why
authority_needed: <role/name level>
sources_for_claims: <list or UNVERIFIED>
status: AWAITING_HUMAN_AUTHORITY
```

Receipt shape when authorized (human already approved outside this skill):
```text
RECEIPT
action: <message_send|spend|mutate_external>
authority_ref: <human id / ticket>
payload_summary: <what ran>
result: <success|partial|failed>
artifacts: <paths>
rollback_hint: <how to undo or suppress>
```

Failure: preserve drafts; do not retry send/spend loops without new authority.
Rollback: prior capability version remains the rollback_target; no history rewrites;
revoked consent re-suppresses immediately.

## 9. Prohibited

Scraping, spam, stealth browser automation, CAPTCHA bypass, automated proposals,
purchases, publishing, or real outreach from fixtures. No personal or client
prospect PII in repo evidence.

## 10. Gate line

End successful deliverables with the literal line: `Gate: passed`
only when consent/suppression/deliverability/platform/attribution checks that
apply to the deliverable are satisfied or explicitly waived by human authority.
