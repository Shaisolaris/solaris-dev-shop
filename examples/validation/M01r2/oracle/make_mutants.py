"""M01 mutants of the G01 guards. Each is one exact, single-occurrence replacement."""
import sys
from pathlib import Path
M = {
 "rv_kind_check": ['    if kind not in FIXTURE_KINDS:\n', '    if False:\n'],
 "rv_kind_or": ['    kind_key = "fixture_kind" if "fixture_kind" in data else "kind" if "kind" in data else None\n    kind = data[kind_key] if kind_key else "packet"\n',
                '    kind_key = "fixture_kind"\n    kind = data.get("fixture_kind") or data.get("kind") or "packet"\n'],
 "mut_kind_precedence": ['kind_key = "fixture_kind" if "fixture_kind" in data else "kind" if "kind" in data else None',
                         'kind_key = "kind" if "kind" in data else "fixture_kind" if "fixture_kind" in data else None'],
 "mut_kinds_empty": ['FIXTURE_KINDS = ("packet",', 'FIXTURE_KINDS = ("", "packet",'],
 "rv_unknown_exp": ['    if unknown:\n', '    if False:\n'],
 "mut_exp_keys": ['EXPECTATION_KEYS = ("outcome", "gate_codes", "accountable_role")', 'EXPECTATION_KEYS = ("outcome", "gate_codes", "accountable_role", "decision")'],
 "rv_outcome": ['    if "outcome" in expected and expected["outcome"] not in EXPECTATION_OUTCOMES:\n', '    if False:\n'],
 "mut_outcome_set": ['EXPECTATION_OUTCOMES = ("pass", "fail_gate")', 'EXPECTATION_OUTCOMES = ("pass", "fail_gate", "fail")'],
 "rv_role": ['    if "accountable_role" in expected and (\n', '    if False and (\n'],
 "mut_role_strip": ['        not isinstance(expected["accountable_role"], str) or not expected["accountable_role"].strip()\n',
                    '        not isinstance(expected["accountable_role"], str)\n'],
 "rv_missing_dir": ['    if not root.is_dir():\n        return _suite_report([], 0, 0, error=f"fixture directory not found: {root}")\n', ''],
 "rv_empty": ['    if not results:\n', '    if False:\n'],
 "mut_ok_error": ['"ok": failed == 0 and error is None,', '"ok": failed == 0,'],
}
src_path, name, out = sys.argv[1], sys.argv[2], sys.argv[3]
src = Path(src_path).read_text()
old, new = M[name]
assert src.count(old) == 1, (name, src.count(old))
Path(out).write_text(src.replace(old, new))
if __name__ == "__main__" and len(sys.argv) > 4:
    print(" ".join(M))
