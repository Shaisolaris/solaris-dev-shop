# 2026 AI-CS shift + continuous-signal health - depth reference

METHODOLOGY absorption (2026-06-13, web-research synthesis; sources: HubSpot 2026 CS-metrics, Perspective AI 2026 platform survey, customerscore.io 2026 churn-prediction, Pylon/Authencio 2026 tooling guides). Gate-0: current rules.md owns the 4-dim/5-dim WEIGHTED health model, segment thresholds, trend matrix, and the calibration loop - but treats scoring as a periodic (monthly/quarterly) batch. This adds the 2026 continuous-listening operating model and the trigger-to-playbook wiring, which the prior model did not specify. No code bundled (methodology only).

## 1. The 2026 break from 2018-era health dashboards
- The legacy model = a quarterly 0-100 dashboard reviewed by a CSM. The 2026 model differs on three axes:
  1. **Continuous, not quarterly** - score on a rolling window, not a calendar review. Use a 14-day rolling login/usage window so decay is caught in days, not at the next QBR.
  2. **Open-ended language, not just 0-10** - capture the customer's own words (ticket text, call transcripts, email sentiment, survey free-text), not only the numeric NPS/CES. The reason behind a score predicts churn better than the score.
  3. **Automated action, not just an alert** - a threshold breach should TRIGGER a specific play, not just color a cell. (Mechanics below.) Solaris stays human-in-the-loop on the SEND, but the trigger-to-draft step is automatable.

## 2. Signal hierarchy (what to weight in 2026)
Lead indicators that move first, in priority order:
1. **Declining logins over a 14-day rolling window** (earliest, strongest leading signal - falls before sentiment does).
2. **Feature-adoption DEPTH** (breadth of features used, not just frequency) - shallow adoption = unrealized value = renewal risk even when logins look fine.
3. **Support-ticket SENTIMENT** (not just volume) - tone and recurring-theme clustering; a spike-then-silence pattern is the classic pre-churn shape.
4. **Renewal-date proximity** as a time-decay multiplier on every other signal (a yellow at T-30 is a red).
These map onto the existing rules.md dimensions (Usage/Engagement/Support/Relationship) - this layer says WHICH sub-signal fires first and how fast to read it.

## 3. Threshold-to-playbook wiring (the missing operational link)
On a score/segment breach, auto-route to the matching play (do not just notify):
- Score drops below segment Yellow -> draft the W3 L1 personal note (CSM reviews + sends within 24h).
- Score drops below segment Red -> raise the same-day internal flag + queue the exec-to-exec outreach (W3 L2).
- Adoption-depth flat for 30d while logins healthy -> trigger a targeted training/enablement play, not a save play (it is a value gap, not a relationship gap).
- Support sentiment turns negative + ticket reopened -> immediate escalation + credit consideration (W3 technical branch).
Keep the routing table version-controlled next to the health log; review the trigger->play mapping in the quarterly calibration loop alongside threshold creep.

## 4. Solaris application (retainer book, no telemetry)
For clients without product telemetry, the continuous-signal model still applies on PROXIES: reply latency (rolling 14-day), deliverable-acceptance turnaround, request-flow volume, and invoice-payment behavior. The shift is the same - watch the rolling trend daily, capture their words, and let a proxy breach trigger the matching play rather than waiting for the next check-in.

## Sources
- HubSpot, "15 customer success metrics that matter in 2026" (blog.hubspot.com/service/customer-success-metrics)
- Perspective AI, "Best AI Customer Success Platforms 2026" (getperspective.ai)
- customerscore.io, "Customer Health Score 2026: Why AI Changes Churn Prediction"
- Pylon, "10 Essential Customer Success Tools for 2026"; Authencio 2026 retention-software guide
