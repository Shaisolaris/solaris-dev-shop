"""M02 r2 mutants of the G02 r2 activate.py (Grok self-validation). Each targets one r2 fix or a core guard.
Usage: python make_mutants_r2v.py SRC_activate.py OUTDIR   (each edit must apply exactly once)"""
import sys
from pathlib import Path
M = {
 "bind_off": ('if journal is not None and journal.get("project_root") != str(root):', 'if False:'),
 "inherit_on_foreign": ('previous = journal["intake"] if journal and not foreign_gap else {}', 'previous = journal["intake"] if journal else {}'),
 "foreign_resume_allowed": ('        if resume:\n            return _result("blocked", root, errors=[head + "; resume refused', '        if False:\n            return _result("blocked", root, errors=[head + "; resume refused'),
 "visible_is_strip": ('return any(not ch.isspace() and unicodedata.category(ch) not in ("Cf", "Cc", "Zs", "Zl", "Zp") for ch in text)', 'return bool(text.strip())'),
 "unresolved_off": ('if deploy is not None and UNRESOLVED_ANSWER.match(deploy):', 'if False:'),
 "journal_entry_types_off": ('for rel, entry in data["files"].items():', 'for rel, entry in []:'),
 "lock_oserror_uncaught": ('except OSError as exc:  # read-only root', 'except FileNotFoundError as exc:  # read-only root'),
 "path_length_off": ('too_long = _path_problem(root_path)', 'too_long = None'),
 "temps_not_removed": ('removed = _remove_leftover_temps(root) if root_kind != "missing" else []', 'removed = []'),
 "temps_greedy": ('if m and m.group("name") in names and _kind(_lstat(d / entry)) == "file":', 'if m and _kind(_lstat(d / entry)) != "missing":'),
 "empty_lock_not_stale": ('if st is not None and st.st_size == 0:', 'if False:'),
 "marker_allowed": ('if not field.endswith("deploy_model") and DEPLOY_MARKER.search(text):', 'if False:'),
 "commit_ids_everywhere": ('rx.search(_without_commit_ids(text) if field == "brief" else text)', 'rx.search(_without_commit_ids(text))'),
 "bare_hex_allowed": ('COMMIT_ID = re.compile(r"(?i)\\b(?:commit|fork|sha|revision|rev)\\b[\\s:#@-]*(?:of\\s+)?([0-9a-f]{40}|[0-9a-f]{64})\\b")', 'COMMIT_ID = re.compile(r"(?i)\\b()([0-9a-f]{40}|[0-9a-f]{64})\\b")'),
 "no_lock": ('    held = _acquire_lock(root)\n', '    held = None\n'),
}
src = Path(sys.argv[1]).read_text(); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
for name, (a, b) in M.items():
    n = src.count(a)
    if n != 1:
        sys.exit(f"anchor for {name} found {n} times")
    (out / f"{name}.py").write_text(src.replace(a, b))
    print("made", name)
