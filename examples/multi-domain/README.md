# Multi Domain walkthrough

An API and landing-page request produces one accountable specialist, with multiple detected domains. Supporting specialists do not execute automatically.

```bash
python control-plane/meta_control_plane.py intake --fixture fixtures/control-plane/multi_domain_intake.json --json
```

The saved [input](input.md) and [actual JSON result](observed.json) were generated from engine 1.1.0. `performed_work` is false. Assignment IDs and timestamps change between runs; the routing decision is deterministic.
