#!/usr/bin/env python3
"""Reproducible provider-free routing correctness and latency benchmark."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import platform
import re
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "control-plane"))
import meta_control_plane as mcp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.iterations < 1:
        parser.error("--iterations must be positive")
    pattern = re.compile(r'^-\s+(ASSIGN|ESCALATE)\s+"([^"]+)"\s+->\s+(\S+)\s*$', re.M)
    probes = pattern.findall((ROOT / "control-plane/routing-probes.md").read_text())
    cases = list(probes)
    for kind, text, expected in probes[:100 - len(cases)]:
        cases.append((kind, "Please, " + text, expected))
    if len(cases) != 100 or len({text for _, text, _ in cases}) != 100:
        raise RuntimeError("benchmark requires 100 distinct requests")
    policy, roster, budgets = mcp.load_policy(), mcp.load_roster(), mcp.load_budgets()
    mcp.intake(cases[0][1], policy=policy, roster=roster, budgets=budgets)
    timings, failures = [], []
    for _ in range(args.iterations):
        for kind, request, expected in cases:
            start = time.perf_counter_ns()
            d = mcp.intake(request, policy=policy, roster=roster, budgets=budgets)
            timings.append((time.perf_counter_ns() - start) / 1_000_000)
            got = d.assignment.primary_capability if d.assignment else d.escalation.reason
            if d.decision != kind.lower() or got != expected or d.performed_work:
                failures.append({"request": request, "expected": expected, "got": got})
    ordered = sorted(timings)
    report = {"engine": mcp.ENGINE_VERSION, "python": platform.python_version(),
              "system": platform.system(), "architecture": platform.machine(),
              "distinct_requests": len(cases), "samples": len(timings),
              "mean_ms": round(statistics.mean(timings), 4),
              "p95_ms": round(ordered[math.ceil(.95 * len(ordered)) - 1], 4),
              "failures": failures, "method": "warm engine; policy/roster preloaded; no model/network calls; CLI startup excluded",
              "source_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                for name in ["control-plane/meta_control_plane.py", "control-plane/policy.json",
                                             "control-plane/routing-probes.md"]}}
    encoded = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded)
    print(encoded, end="")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
