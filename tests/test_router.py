#!/usr/bin/env python3
"""Routing regression suite (CODE-01/06/08).

Parses control-plane/routing-probes.md (the source of truth) and runs every
probe against the intake engine. stdlib unittest, no dependencies.

Usage:
  python3 tests/test_router.py
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "control-plane"))

import meta_control_plane as mcp  # noqa: E402

PROBE_RE = re.compile(r'^-\s+(ASSIGN|ESCALATE)\s+"([^"]+)"\s+->\s+(\S+)\s*$')


def load_probes():
    probes = []
    text = (ROOT / "control-plane" / "routing-probes.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        m = PROBE_RE.match(line.strip())
        if m:
            probes.append((m.group(1), m.group(2), m.group(3)))
    return probes


class TestRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = mcp.load_policy()
        cls.roster = mcp.load_roster()
        cls.budgets = mcp.load_budgets()

    def test_roster_covers_all_employees(self):
        disk = set()
        for cat in (ROOT / "employees").iterdir():
            if not cat.is_dir():
                continue
            for emp in cat.iterdir():
                if emp.is_dir() and (emp / "SKILL.md").exists() and emp.name != "assurance":
                    disk.add(f"solaris.{emp.name}")
        active = {
            c["id"] for c in self.roster.get("capabilities", [])
            if c.get("status") == "active" and c["id"].startswith("solaris.")
        }
        self.assertEqual(active, disk, "roster must cover exactly the 61 employee dirs")

    def test_no_phantom_capabilities_in_policy(self):
        active = {c["id"] for c in self.roster.get("capabilities", []) if c.get("status") == "active"}
        for cap in self.policy.get("domain_to_capability", {}).values():
            self.assertIn(cap, active, f"domain_to_capability -> phantom {cap}")
        for cap in self.policy.get("domain_accountable", {}).values():
            self.assertIn(cap, active, f"domain_accountable -> phantom {cap}")
        for rule in self.policy.get("route_overrides", []):
            for cap in rule.get("capabilities", []):
                self.assertIn(cap, active, f"route_override -> phantom {cap}")
        for cap in self.policy.get("capability_keywords", {}):
            self.assertIn(cap, active, f"capability_keywords -> phantom {cap}")

    def test_probes(self):
        probes = load_probes()
        self.assertGreaterEqual(len(probes), 66, "expected 61 employee probes + 5 edge probes")
        failures = []
        for kind, text, expected in probes:
            d = mcp.intake(text, policy=self.policy, roster=self.roster, budgets=self.budgets)
            if kind == "ASSIGN":
                got = d.assignment.primary_capability if d.assignment else None
                if d.decision != "assign" or got != expected:
                    failures.append(f"{text!r}: expected assign->{expected}, got {d.decision}->{got}")
            else:
                got = d.escalation.reason if d.escalation else None
                if d.decision != "escalate" or got != expected:
                    failures.append(f"{text!r}: expected escalate/{expected}, got {d.decision}/{got}")
            if d.performed_work:
                failures.append(f"{text!r}: performed_work must be False")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_supporting_budget_enforced(self):
        policy = dict(self.policy)
        # Force a many-supporting override to test truncation
        policy["route_overrides"] = [{
            "keywords": ["zzz-budget-probe"],
            "keywords_all": [],
            "capabilities": ["solaris.backend-developer"] + [f"solaris.e{i}" for i in range(10)],
        }]
        roster = {"capabilities": [{"id": "solaris.backend-developer", "status": "active"}] +
                  [{"id": f"solaris.e{i}", "status": "active"} for i in range(10)]}
        d = mcp.intake("zzz-budget-probe build this now please", policy=policy,
                       roster=roster, budgets=self.budgets)
        self.assertEqual(d.decision, "assign")
        self.assertLessEqual(len(d.assignment.supporting), 5)
        self.assertTrue(d.budgets_applied.get("supporting_truncated_to_max"))

    def test_multi_domain_accountable_is_specialist(self):
        d = mcp.intake("Build a REST API and a marketing landing page for the client portal",
                       policy=self.policy, roster=self.roster, budgets=self.budgets)
        self.assertEqual(d.decision, "assign")
        self.assertNotEqual(d.assignment.accountable, "meta.chief-of-staff")
        self.assertTrue(d.assignment.accountable.startswith("solaris."))


if __name__ == "__main__":
    unittest.main(verbosity=2)
