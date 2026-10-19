#!/usr/bin/env python3
"""Control for binding_oracle.py: accepts everything. Every packet passes, every closure is allowed."""
import sys
from types import SimpleNamespace

ACCOUNTABLE_GATES = {"functional": "qa-engineer"}


def evaluate_artifact_packet(packet):
    return SimpleNamespace(ok=True, status="pass", gate_codes=[], messages=[], evidence={})


def can_close_finding(finding, **kw):
    return True, []


if __name__ == "__main__":
    print("{}")
    sys.exit(0)
