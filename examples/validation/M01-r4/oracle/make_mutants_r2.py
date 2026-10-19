"""M01 r2 mutants (Grok self-validation): the 13 r1 mutants re-anchored on deb06f6 plus one mutant per
G01-repair guard. Each is one exact, single-occurrence replacement; the generator asserts count == 1.
Usage: make_mutants_r2.py SRC NAME OUT | make_mutants_r2.py --list"""
import sys
from pathlib import Path
R1 = {
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
R2 = {  # one per repair guard (F1..F5)
 "f1_near_off": ['        if near:\n            return f"fixture key', '        if False:\n            return f"fixture key'],
 "f1_norm_only": [' or difflib.SequenceMatcher(None, key.lower(), c).ratio() >= 0.8]', ']'],
 "f1_ratio_095": ['.ratio() >= 0.8]', '.ratio() >= 0.95]'],
 "f1_stray_off": ['stray = [k for k in NON_PACKET_FIXTURE_KEYS if k in data]', 'stray = []'],
 "f1_extra_off": ['extra = sorted(k for k in data if k not in allowed)', 'extra = []'],
 "f1_dup_off": ['            raise ValueError(f"duplicate key {key!r}")\n', '            pass\n'],
 "f2_gate_any": ['missing = [g for g in want if g not in result.gate_codes]', 'missing = [] if any(g in result.gate_codes for g in want) else want'],
 "f2_gate_nonempty_off": ['    if "gate_codes" in expected and not expected["gate_codes"]:\n', '    if False:\n'],
 "f2_gate_outcome_off": ['    if "gate_codes" in expected and expected.get("outcome") != "fail_gate":\n', '    if False:\n'],
 "f2_role_vacuous": ['    if exp_role and not result.findings:\n', '    if False:\n'],
 "f3_legal_default_off": ['        if not expected:\n            expected = {"outcome": "fail_gate"}\n', ''],
 "f4_fresh_bool": ['if isinstance(fresh, bool) or not isinstance(fresh, int)', 'if not isinstance(fresh, int)'],
 "f4_fresh_neg": [' or fresh < 0:', ':'],
 "f4_text_type_off": ['if key in data and not isinstance(data[key], str):', 'if False:'],
 "f4_defect_type_off": ['        if "defect" in data and not isinstance(data["defect"], dict):\n', '        if False:\n'],
 "f4_generic_except_off": ['    except Exception as exc:  # noqa: BLE001', '    except ZeroDivisionError as exc:  # noqa: BLE001'],
 "f4_outer_recursion_off_EQUIV": ['    except RecursionError:\n        return _invalid_packet("fixture is nested too deeply")\n', ''],
 "f5_case_suffix": ['f.lower().endswith(".json")', 'f.endswith(".json")'],
 "f5_symlink_report_off": ['                linked_dirs.append(Path(dirpath, d))\n', '                pass\n'],
}
M = {**R1, **R2}
if sys.argv[1] == "--list":
    print(" ".join(M)); sys.exit(0)
src_path, name, out = sys.argv[1:4]
src = Path(src_path).read_text()
old, new = M[name]
assert src.count(old) == 1, (name, src.count(old))
Path(out).write_text(src.replace(old, new))
