#!/usr/bin/env python3
"""Control for binding_oracle.py: the real engine with revision binding ignored.

Packets have their subject and every reviewed binding removed before evaluation, closures ignore the
revisions they are given and a closed finding always counts as current. This is the behaviour before G05
with the new names present. The oracle must reject it."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "employees", "quality-security", "assurance"))
import quality_os as _q  # noqa: E402
from quality_os import *  # noqa: E402,F401,F403

_evaluate, _can, _close = _q.evaluate_artifact_packet, _q.can_close_finding, _q.close_finding


def evaluate_artifact_packet(packet):
    if isinstance(packet, dict):
        packet = dict(packet)
        packet.pop("subject", None)
        if isinstance(packet.get("evidence"), dict):
            packet["evidence"] = {g: ({k: v for k, v in r.items() if k != "reviewed"} if isinstance(r, dict) else r)
                                  for g, r in packet["evidence"].items()}
    return _evaluate(packet)


def can_close_finding(finding, **kw):
    kw.pop("subject_revision", None)
    kw.pop("verified_revision", None)
    return _can(finding, **kw)


def close_finding(finding, **kw):
    rev = kw.get("verified_revision") or kw.get("subject_revision") or ""
    kw.pop("subject_revision", None)
    kw.pop("verified_revision", None)
    updated, codes = _close(finding, **kw)
    if not codes:
        updated.closed_at_revision = rev
    return updated, codes


def closure_is_current(finding, current_revision):
    return (finding.status == "closed", [] if finding.status == "closed" else ["NOT_CLOSED"])


_q.evaluate_artifact_packet = evaluate_artifact_packet
_q.can_close_finding = can_close_finding

if __name__ == "__main__":
    sys.exit(_q.main())
