# Escalation walkthrough

A production outage is escalated to the owner before any assignment or specialist execution. This is an authority decision, not an outage repair.

```bash
python control-plane/meta_control_plane.py intake --fixture fixtures/control-plane/high_risk_outage.json --json
```

The saved [input](input.md) and [actual JSON result](observed.json) were generated from engine 1.1.0. `performed_work` is false. Assignment IDs and timestamps change between runs; the routing decision is deterministic.
