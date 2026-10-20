# G31: customer scope to delivery acceptance (business analyst, sales engineer, proposal writer)

Tool: `employees/product-project/business-analyst/scope_acceptance.py` (stdlib, Python 3.9+, local files
only). Rules and package format: `employees/product-project/business-analyst/scope-estimate-acceptance.md`.
All data here is synthetic. Nothing is sent to a customer; reports are drafts for the owner.

## Demo (from the repository root)

```bash
python3 employees/product-project/business-analyst/scope_acceptance.py check examples/capabilities/G31/fixtures/portal.json   # exit 0
python3 employees/product-project/business-analyst/scope_acceptance.py check examples/capabilities/G31/fixtures/portal.json --json   # exit 0
python3 employees/product-project/business-analyst/scope_acceptance.py accept examples/capabilities/G31/fixtures/portal.json examples/capabilities/G31/fixtures/delivery.json   # exit 0
python3 examples/capabilities/G31/scope_oracle.py   # ACCEPTED 12/12
python3 examples/capabilities/G31/scope_oracle.py --tool examples/capabilities/G31/naive_scope.py   # REJECTED 1/12
python3 examples/capabilities/G31/scope_oracle.py --tool examples/capabilities/G31/noop_scope.py   # REJECTED 1/12
```

## The clinic portal fixture, worked by hand

In scope: R1 booking (120/160/220 h), R2 front desk view (60/80/110), R3 reminders (30/40/60), R4 CSV import
(20/30/50). Sums: **230 / 310 / 440 hours**; at 150.00 per hour the range is **34,500.00 to 66,000.00 USD**.
R5 (board reports) is optional and listed as excluded. R2 says "real-time", which is vague; AMB1 escalated it
to the clinic operations manager and records the resolution (refresh within 60 s), so it does not block.
R4 rests on A2 (one CSV under 50,000 rows), which is unconfirmed: allowed in a range estimate and reported as
a condition of C1, C2 and C3, but a fixed price of 66,000.00 is refused until A2 is confirmed.

The date commitment C3 (live by 2027-02-12) relies on the G17 studio decision in `fixtures/capacity`: option
descope-reporting is feasible in the downside and the launch finishes in week 18. With the calendar starting
2026-10-05, week 18 ends 2026-10-05 + 125 days = **2027-02-07**, before 2027-02-12. Moving C3 to 2027-02-06,
using the as-is or contractors option, or editing the stored G17 result blocks the proposal.

`fixtures/delivery.json` carries a passing result with a pinned evidence file for each criterion AC1 to AC5,
so `accept` reports every in-scope requirement accepted.

## Oracle

`scope_oracle.py` copies the fixtures to a temporary folder and checks: the clean figures and trace matrix
(o1); invented, unknown-ref and out-of-scope commitments (o2); estimate arithmetic to the cent and fixed-price
support (o3); vague wording, unmeasured criteria and open escalations (o4); demo evidence that is changed,
missing, failing or future-dated (o5); the G17-backed date (o6); acceptance with failing, missing and edited
evidence and a not-ready scope (o7); 11 invalid packages and an unknown delivery criterion refused with
nothing written (o8); `--out`, `verify`, tampered and truncated results and keeping an earlier result after a
failed run (o9); 12 seeded unseen packages of 120 to 200 requirements with planted flaws whose findings are
known by construction (o10); contradictions (seeded phrasings from six family pairs): requirement vs
requirement, requirement vs its own input, a commitment text, a declared `conflicts_with` and an open
escalation all block, and an owner-resolved one is ready with `qualified_by` on the affected commitments;
no false hit on "onboarding" (o11); no network, mail or process use and fixtures byte-identical (s1). `--seed N`
changes the unseen packages. The naive control (template checklist) and the no-op control both fail.
