#!/usr/bin/env python3
"""Build deliberately broken copies of the candidate activate.py for oracle teeth checks.

Usage: python make_mutants.py <path/to/activate.py> <out-dir>
Each mutant is <out-dir>/<name>/activate.py. Every replacement must apply exactly once,
so a mutant can never silently equal the original.
"""
import sys
from pathlib import Path

M = {
    "overwrite_owner_files": [('            artifacts[rel] = "conflict_preserved"', '            artifacts[rel] = "update"')],
    "blank_deploy_defaults_live": [('deploy = _check_text("deploy_model", raw.get("deploy_model"), problems, required=False)',
                                    'deploy = _check_text("deploy_model", raw.get("deploy_model"), problems, required=False) or "main=live"')],
    "blank_deploy_confirmed": [
        ('deploy = _check_text("deploy_model", raw.get("deploy_model"), problems, required=False)',
         'deploy = raw.get("deploy_model") if isinstance(raw.get("deploy_model"), str) and not raw.get("deploy_model").strip() '
         'else _check_text("deploy_model", raw.get("deploy_model"), problems, required=False)'),
        ('    if intake["deploy_model"]:\n        return f"DEPLOY-MODEL:', '    if intake["deploy_model"] is not None:\n        return f"DEPLOY-MODEL:'),
        ('    if not intake["deploy_model"]:\n        gaps.append("Deploy model unresolved', '    if intake["deploy_model"] is None:\n        gaps.append("Deploy model unresolved')],
    "follow_symlinks": [("        return os.lstat(path)", "        return os.stat(path)")],
    "stage_in_owner_repo": [('        info["modified"] = False\n', '        info["modified"] = False\n        _git(root, "add", "-A")\n')],
    "swallow_write_error": [('        return _result("failed", root, intake=intake, intake_changes=changes',
                             '        return _result("complete", root, intake=intake, intake_changes=changes')],
    "no_lock": [('    """Create the per-project lock exclusively. Returns an error text when it is held."""\n',
                 '    """Create the per-project lock exclusively. Returns an error text when it is held."""\n    return None\n')],
    "resume_is_noop": [("    if resume:\n        if journal is None:",
                        "    if resume and journal is not None:\n        return _result(\"complete\", root)\n    if resume:\n        if journal is None:")],
    "stale_plan_kept": [('        elif cur in known:\n            artifacts[rel] = "update"',
                         '        elif cur in known and rel == PLAN:\n            artifacts[rel] = "unchanged"\n'
                         '        elif cur in known:\n            artifacts[rel] = "update"')],
    "within_ignored": [("    if within is not None:\n        boundary", "    if False and within is not None:\n        boundary")],
    "predictable_temp": [
        ('flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)',
         'flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC'),
        ('tmp = target.parent / f".{target.name}.{secrets.token_hex(8)}.activation-tmp"', 'tmp = target.parent / f".{target.name}.tmp"')],
    "secret_check_location_only": [("    for label, rx in SECRET_PATTERNS:\n        if rx.search(text):",
                                    "    for label, rx in (SECRET_PATTERNS if field.endswith('location') else ()):\n        if rx.search(text):")],
    "no_intent_journal": [("        if something_to_do:\n            current = JOURNAL\n            save_journal()\n            current = None\n", "")],
}


def main(src, out):
    text = Path(src).read_text()
    for name, reps in M.items():
        t = text
        for old, new in reps:
            n = t.count(old)
            if n != 1:
                raise SystemExit(f"{name}: pattern found {n} times: {old[:60]!r}")
            t = t.replace(old, new)
        d = Path(out) / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "activate.py").write_text(t)
        print(name)


if __name__ == "__main__":
    main(*sys.argv[1:3])
