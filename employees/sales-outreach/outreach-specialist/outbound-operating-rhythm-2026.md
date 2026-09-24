# Outbound operating rhythm + incident response + pre-send list grading - depth reference

METHODOLOGY absorption (2026-06-13). Source: github.com/growthenginenowoslawski/coldoutboundskills (392 stars, MIT, last commit 2026-05-04). Methodology only - the repo's TypeScript scripts (audit-performance.ts, score-list.ts, run-spam-test.ts) are NOT bundled; treat them as optional self-host tooling. Gate-0 PASS: the employee owned per-touch CADENCE (Day 0/3/7/14/21-28) and the deliverability HARD RULES (SPF/DKIM/DMARC, 5k/day, complaint thresholds) but had no ongoing OPERATING RHYTHM, no incident-response decision tree, and no pre-send list-quality grade. This adds the run-it-continuously layer.

## 1. Operating rhythm (what separates hobbyist from top-1% = consistency, not tooling)
Put these on the calendar as recurring events; the calendar is the accountability system (no built-in reminder by design - a silent reminder failure = silent ops failure):
- **Monday - deliverability audit (15 min):** fleet reply rate over trailing 7 days must be >=1% (the 1% rule); pull flagged campaigns (low reply) and flagged inboxes (high bounce); act before sending more.
- **Wednesday - positive-reply sweep:** triage every positive reply, ensure <1h SLA was met, push warm threads to Sales Engineer with signal + objection context.
- **Friday - campaign retrospectives:** one variable per active test, read results, kill or scale.
- **Biweekly - inbox rotation:** rest/rotate inboxes to protect per-inbox reputation; scale by adding inboxes, not per-inbox volume.
- **Monthly - spam-placement test:** seed-list inbox-placement check; <70% placement = real deliverability issue, >85% = look at copy/targeting instead.
- **Quarterly - experiment review:** roll up the quarter's A/B results into the playbook; retire losing angles.

## 2. Deliverability incident-response (triage tree, was: only prevention rules)
Five incident types, each with first-action + fix-time:
| Symptom | Likely cause | First action | Fix time |
|---|---|---|---|
| Reply rate dropped sharply | Emails landing in spam | Run spam-placement test | 1-14 days |
| Bounce >3% | Bad list OR domain reputation | Check bounce TYPES (hard vs soft) | 1-3 days |
| Domain blacklisted | Shared-IP bad actor OR your domain flagged | Check blacklists, rotate if needed | 7-30 days |
| Inbox blocked in warmup | Warmup network flagged sending pattern | Pause, investigate, maybe replace | 1-7 days |
| Gmail marks as promotional | Content triggers (links/images/HTML) | Simplify content | 1-3 days |

"My reply rate dropped" decision tree:
1. **Quantify** - is this week <50% of the trailing 4-week average? No -> noise, wait a week. Yes -> real, continue.
2. **Scope** - ALL campaigns dropping (fleet-level: infra or a shared copy pattern) or ONE (campaign-level: targeting/copy/list)?
3. **Fleet-wide** - run the spam-placement test first: inbox placement <70% = real deliverability issue (fix infra/auth/warmup); >85% = deliverability is fine, look at copy/targeting.

## 3. Pre-send list-quality scorecard (net-new gate before any send)
A CSV of 5,000 leads is not a good list of 5,000 leads. Grade EVERY list before upload (catches the 3 top failure modes - bad list, unverified emails, ICP drift - in ~5 min). Score 8 dimensions, each 0-100, roll to a letter grade A+..F:
1. Duplicate rate (dedupe against CRM + within-list)
2. Title diversity (not all one title)
3. Bad-title patterns (generic/role-mismatch/seniority noise)
4. Catch-all domain density (catch-alls inflate "valid" but bounce)
5. ICP fit vs the declared ICP filters (headcount/industry/seniority)
6. Email-verification coverage (every address verified; B2B data decays ~2.1%/mo)
7. Seniority match (targeting VPs but list is mostly Managers = ICP drift)
8. Company-fit completeness (domain/industry/headcount present)
Output: letter grade + top-5 issues + a pre-send checklist. Do not send a list below a B without remediation.

## Sources
- github.com/growthenginenowoslawski/coldoutboundskills (MIT) - skills/cold-email-weekly-rhythm, skills/deliverability-incident-response, skills/list-quality-scorecard (methodology lifted; scripts left upstream as optional self-host tooling).
