# G32: customer success and consent-aware follow-through (drafts only)

Tool: `employees/sales-outreach/customer-success/followthrough.py` (stdlib, Python 3.9+, POSIX). Rules:
`employees/sales-outreach/customer-success/consent-follow-through.md`. It builds on the G04 hash-chained
journal and lock (`employees/infrastructure/fleet-dispatcher/handoff.py`). All data is synthetic, contacts
carry opaque handles, and nothing is sent.

## Demo (from the repository root, with STATE an empty temporary folder)

```bash
python3 employees/sales-outreach/customer-success/followthrough.py run $STATE --account examples/capabilities/G32/fixtures/account.json --events examples/capabilities/G32/fixtures/events.jsonl --now 2026-10-02T12:00:00-07:00 --worker w1   # exit 0
python3 employees/sales-outreach/customer-success/followthrough.py run $STATE --account examples/capabilities/G32/fixtures/account.json --events examples/capabilities/G32/fixtures/events.jsonl --now 2026-10-05T12:00:00-07:00 --worker w2   # exit 0
python3 employees/sales-outreach/customer-success/followthrough.py run $STATE --account examples/capabilities/G32/fixtures/account.json --events examples/capabilities/G32/fixtures/events.jsonl --now 2026-10-08T12:00:00-07:00 --worker w1   # exit 0
python3 employees/sales-outreach/customer-success/followthrough.py status $STATE   # exit 0
python3 examples/capabilities/G32/followthrough_oracle.py   # ACCEPTED 10/10
python3 examples/capabilities/G32/followthrough_oracle.py --tool examples/capabilities/G32/naive_followthrough.py   # REJECTED 1/10
python3 examples/capabilities/G32/followthrough_oracle.py --tool examples/capabilities/G32/noop_followthrough.py   # REJECTED 1/10
```

## The fixture, worked by hand

Account northwind-clinic, owner Morgan; contacts Ana, Ben and Dee consented, Cy's consent is unknown.

- **Run 1 (Oct 2, worker w1)**: drafts welcome for Ana, Ben and Dee and the acknowledgement of Ben's ticket
  T1. Cy's three onboarding steps are suppressed (no recorded consent). Seven steps are scheduled.
- **Run 2 (Oct 5, worker w2, the handoff)**: Priya became owner on Oct 5, so the three unsent drafts are
  re-rendered for her (reassigned). Dee opted out of marketing on Oct 3: her welcome draft is withdrawn and her
  check-in and training are suppressed. Ana replied on Oct 4, cancelling her check-in; Ben replied to the first
  agent response, cancelling that nudge. New drafts: Ben's check-in and the nudge for the second response.
- **Run 3 (Oct 8, worker w1)**: Ben's ticket closed on Oct 6, so the open nudge is withdrawn and a feedback
  request is drafted; Ana's and Ben's training invites are drafted. Dee's opt_in on Oct 6 is reported as
  consent_review_required and she stays suppressed.

End state: 9 draft files, 7 open (all signed by Priya) and 2 withdrawn (Dee's welcome, Ben's second nudge);
sent 0. Running any step again drafts nothing new.

## Oracle

`followthrough_oracle.py` compares the tool against an independent reference simulation of the playbook: the
fixture over three runs (o1); reruns and redelivered events (o2); permanent suppression with opt_in, hard
bounce and support to a marketing opt-out (o3); crash drills after the draft and after the ledger record (o4);
8 concurrent workers per run (o5); ownership handoff and status (o6); invalid inputs, a forged journal and
another account's state (o7); a held lock and a torn ledger tail (o8); 3 seeded unseen accounts of 120 to 180
contacts with their generated event logs over 4 runs (o9); no mail, network or process use (s1). The naive control
(due dates only, no ledger) and the no-op control both fail.
