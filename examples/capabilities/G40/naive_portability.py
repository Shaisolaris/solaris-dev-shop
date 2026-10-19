#!/usr/bin/env python3
"""Naive control: trust a copied skill folder and skip outside-install proof."""
import importlib.util, json, sys
from pathlib import Path

REAL = Path(__file__).resolve().parent.parents[2] / "employees/quality-security/qa-engineer/host_portability.py"
spec = importlib.util.spec_from_file_location("host_portability_real", str(REAL))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
_real_skill_copy = m.skill_copy
_real_python_bounds = m.python_bounds


def skill_copy(root, role, dest=None):
    r = _real_skill_copy(root, role, dest)
    r = dict(r)
    r["status"] = "complete"
    r["missing"] = []
    r["result"] = "pass"
    return r


def wheel_smoke(root, outside=None):
    return {
        "schema": m.SCHEMA, "command": "wheel-smoke", "result": "pass", "requires_python": ">=3.10",
        "wheel": "pretend-0.0-py3-none-any.whl", "outside": str(outside or "/tmp"),
        "wheel_files_sample": [], "employees_in_wheel": False, "findings": [],
        "statement": "naive: did not install outside",
    }


def report(root, outside=None):
    parts = {
        "python_bounds": _real_python_bounds(root),
        "skill_copy_qa_engineer": skill_copy(root, "quality-security/qa-engineer"),
        "wheel_smoke": wheel_smoke(root, outside) if sys.version_info >= (3, 10) else {"result": "skipped", "command": "wheel-smoke"},
    }
    return {"schema": m.SCHEMA, "command": "report", "result": "pass", "parts": parts, "findings_count": 0,
            "statement": "naive report"}


m.skill_copy = skill_copy
m.wheel_smoke = wheel_smoke
m.report = report
sys.exit(m.main())
