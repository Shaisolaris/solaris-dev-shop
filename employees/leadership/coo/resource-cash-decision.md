# Resource and cash decision check (resource_decision.py, G17)

For synthetic or exported planning data on local files. It evaluates staffing options for a dated milestone
week by week under a base case and a downside case, rejects or narrows plans that the stated capacity,
dependencies or cash buffer cannot carry, and names the binding constraint. It never picks an option: the
named decision owner decides. Nothing is sent, hired, bought or booked.

```bash
T=employees/leadership/coo/resource_decision.py
python3 $T evaluate package.json                  # readable decision record
python3 $T evaluate package.json --json --out r.json
python3 $T verify package.json r.json             # rerun and compare every figure
```

Exit codes: 0 at least one option is feasible in the downside case; 1 none is (rejected as stated, with
narrowed alternatives) or required evidence is blocked; 2 invalid package, nothing written. verify: 0
identical, 1 differences listed.

## Package (schema solaris.resource-decision/1)

- `decision`: question, owner (required: a decision without an owner is a memo), as_of, currency.
- `assumptions`: every quantity, by name, with `value`, `source`, `dated` (not after as_of), optional `low`
  and `high`, `unit`, `exact: true` for definitions and contract terms, and `downside: low|high` when one
  figure is used where both directions are adverse (for example a hire start date drives both capacity and
  cost). Literal numbers anywhere else are refused. `from_g14: {package, measure}` takes the value from a G14
  reconciliation (`monthly_net_cash` scaled from the period length, or `closing_ar_owed`) in the decision
  currency; books that do not reconcile cleanly block the decision (status `blocked_evidence`).
- `capacity`: per role people, hours_per_week and focus (focus above 0.85 is warned).
- `work`: id, role, hours, `after` (dependencies), priority (lower first), optional `max_people`.
- `milestones`: id, needs (work ids), deadline_week.
- `cash`: opening, monthly_inflow, monthly_outflow, min_buffer_months.
- `options`: id, label, `reversible` with `undo` {weeks, cost} or `why_irreversible`; optional
  capacity_add (role, people, from_week, ramp_weeks at half capacity, until_week), one_time_cost,
  monthly_cost, cost_from_week, cost_until_week, descope (with its dependents), deadline_shift_weeks.
- `risks`: id, text, owner, mitigation, probability, optional extra_hours on a work item and cost; applies_to.
- `dissent`: recorded objections, echoed in the record.

## Rules
- **Downside is one consistent world**: each assumption takes its adverse bound (more hours, fewer people,
  less focus, later start, less inflow, more cost) and every risk is realised. Feasibility is judged on the
  downside; the base case is shown beside it.
- **Schedule**: each week, each role's capacity goes to ready work in priority order, capped by max_people;
  work starts the week after its dependencies finish. A missed milestone names its cause: `dependencies`
  (the chain alone, with unlimited people, is too long), `capacity` (role short N hours by the deadline) or
  `sequencing` (hours suffice but order and caps finish it late).
- **Cash**: weekly, monthly figures x 12/52, exact fractions, cents at the end. The buffer is
  min_buffer_months of the outflow in force that week; the first week below it is reported.
- **Narrowing**: an infeasible option first drops work no milestone needs, lowest priority first, and reruns;
  otherwise it reports the earliest milestone weeks or the cash breach and leaves the trade-off to the owner.
- **Ordering, not a recommendation**: options feasible in the downside are listed reversible first, then by
  the highest lowest-cash point. If only irreversible options survive, the status says so.
- **Decision record**: facts (sources, dates), assumptions, options, risk, dissent, decision_owner and
  required_evidence (unranged figures, stale figures over 180 days, blocked evidence), plus the certainty
  limit: computed from stated assumptions only; not a forecast.

## Limits
- One currency per decision; no FX. Capacity is hours, not skills inside a role. No learning curves beyond the
  half-capacity ramp, no attrition, no partial-week effort dependencies. Risk realisation is all-or-nothing in
  the downside; probabilities only weight the listed exposure.
