# Intake performance

Reproduce the provider-free routing benchmark from a checkout with Python 3.10+:

```bash
python benchmarks/intake.py --iterations 5 --output docs/benchmark.json
```

The corpus contains all 66 canonical specialist/safety probes and 34 distinct
polite-prefix variants: 100 requests, repeated five times for 500 samples. The
benchmark validates the expected specialist or escalation reason, not just time.
It exits nonzero on a routing mismatch or unexpected work execution.

The checked-in [result JSON](benchmark.json) records the actual Python version,
OS, architecture, mean and nearest-rank p95, plus source hashes. Numbers depend
on the host. It measures a warm engine with preloaded policy, roster and budgets;
it excludes process startup, disk loading, provider latency and specialist work.
It is not a production API throughput or model-quality benchmark.

The router is deterministic and does not invoke a model. Cross-provider accuracy
or latency numbers would therefore measure a different layer: how a host agent
uses a skill after routing. No such measurements are claimed here. Issue #19
remains open for a separately designed, authorized provider benchmark.
