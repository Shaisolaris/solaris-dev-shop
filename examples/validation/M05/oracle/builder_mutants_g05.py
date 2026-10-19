M = [
 ("stale_ignored", '''            if state == "stale":
                codes.append("STALE_GATE_EVIDENCE")''', '''            if state == "stale":
                pass'''),
 ("unbound_ignored", '''            elif state == "unbound":
                codes.append("UNBOUND_GATE_EVIDENCE")''', '''            elif state == "unbound":
                pass'''),
 ("digest_change_ignored", 'changed = sorted(p for p in rd if p in sd and rd[p] != sd[p])', 'changed = []'),
 ("revision_trumps_digests", '''    changed = sorted(p for p in rd if p in sd and rd[p] != sd[p])
    if changed:''', '''    changed = sorted(p for p in rd if p in sd and rd[p] != sd[p])
    if changed and not (reviewed.get("revision") and reviewed.get("revision") == subject.get("revision")):'''),
 ("no_carry_forward", '    if rd and all(p in sd for p in rd):\n        return "carried_forward"', '    if False:\n        return "carried_forward"'),
 ("carry_any_digest", 'if rd and all(p in sd for p in rd):', 'if rd and any(p in sd for p in rd):'),
 ("revision_differs_unbound", '''    if rr and sr:
        return "stale", {"revision_changed": True}''', '''    if rr and sr:
        return "unbound", {"reason": "x"}'''),
 ("prefix_any_length", 'return len(short) >= 7 and full.startswith(short)', 'return full.startswith(short)'),
 ("prefix_off", 'return len(short) >= 7 and full.startswith(short)', 'return False'),
 ("sha256_prefix_EQUIV", '''    if a.startswith("sha256:") or b.startswith("sha256:"):
        return False
''', ''),
 ("revision_re_loose", 'REVISION_RE = re.compile(r"^(?:[0-9a-f]{7,64}|sha256:[0-9a-f]{64})$")', 'REVISION_RE = re.compile(r"^\\S+$")'),
 ("subject_unvalidated", '''        subject_errors = binding_errors(packet["subject"], "subject")''', '''        subject_errors = [] if isinstance(packet["subject"], dict) else ["x"]'''),
 ("reviewed_unvalidated", '''                    errors.extend(binding_errors(art["reviewed"], "reviewed"))''', '''                    pass'''),
 ("extra_keys_ok", '''    if extra:
        errors.append''', '''    if False:
        errors.append'''),
 ("empty_binding_ok", '''    if not any(k in value for k in BINDING_KEYS):''', '''    if False:'''),
 ("digest_path_unchecked", 'if not _artifact_path_ok(k) or not isinstance(v, str) or not DIGEST_RE.match(v)]', 'if not isinstance(v, str) or not DIGEST_RE.match(v)]'),
 ("dotdot_ok", 'all(part not in ("", ".", "..") for part in path.split("/"))', 'True'),
 ("max_artifacts_off", 'if not isinstance(digests, dict) or not digests or len(digests) > MAX_BOUND_ARTIFACTS:', 'if not isinstance(digests, dict) or not digests:'),
 ("conflict_off", '''        if len(distinct) > 1:
            codes.append("REVISION_CONFLICT")''', '''        if False:
            codes.append("REVISION_CONFLICT")'''),
 ("conflict_exact", '            if not any(same_revision(r, d) for d in distinct):', '            if r not in distinct:'),
 ("closure_stale_off", '''        if not same_revision(verified_revision, subject_revision):
            return False, ["STALE_CLOSURE_EVIDENCE"]''', '''        if False:
            return False, ["STALE_CLOSURE_EVIDENCE"]'''),
 ("closure_missing_ok", '''        if verified_revision is None:
            return False, ["MISSING_VERIFIED_REVISION"]''', '''        if False:
            return False, ["MISSING_VERIFIED_REVISION"]'''),
 ("closure_rev_unvalidated", '''        if value is not None and revision_error(value):
            return False, ["INVALID_REVISION"]''', '''        if False:
            return False, ["INVALID_REVISION"]'''),
 ("waiver_needs_revision", '''    if finding.status == "waived":
        # Valid waiver closure''', '''    if finding.status == "waived" and (subject_revision is None or verified_revision == subject_revision):
        # Valid waiver closure'''),
 ("closed_at_not_recorded", '        updated.closed_at_revision = verified_revision or ""', '        updated.closed_at_revision = ""'),
 ("current_ignores_revision", '''    if not same_revision(closed_at, current_revision):
        return False, ["STALE_CLOSURE"]''', '''    if False:
        return False, ["STALE_CLOSURE"]'''),
 ("unbound_closure_current", '''    if not isinstance(closed_at, str) or not closed_at:
        return False, ["UNBOUND_CLOSURE"]''', '''    if not isinstance(closed_at, str) or not closed_at:
        return True, []'''),
 ("reopen_keeps_closer", '    updated.closed_by_role = ""\n    updated.closed_at_revision = ""', '    updated.closed_at_revision = ""'),
 ("reopen_drops_evidence", '    updated.evidence = list(finding.evidence) + [note]', '    updated.evidence = [note]'),
 ("reopen_any_status", '''    if finding.status != "closed":
        return copy.deepcopy(finding), ["NOT_CLOSED"]''', '''    if False:
        return copy.deepcopy(finding), ["NOT_CLOSED"]'''),
 ("reopen_short_reason", 'if not _nonblank(reason) or len(reason.strip()) < MIN_WAIVER_JUSTIFICATION:', 'if not _nonblank(reason):'),
 ("digest_symlink_ok", '''        if p.is_symlink():
            raise ValueError(f"{rel} is a symlink''', '''        if False:
            raise ValueError(f"{rel} is a symlink'''),
 ("digest_size_unbounded", '        if p.stat().st_size > MAX_DIGEST_FILE_BYTES:', '        if False:'),
 ("digest_empty_ok", '''    if not out:
        raise ValueError("no files to digest")''', ''),
 ("digest_unsorted_EQUIV", '                for name in sorted(filenames):', '                for name in reversed(sorted(filenames)):'),
 ("digest_cli_rev_unchecked", '''        if args.revision is not None and revision_error(args.revision):''', '''        if False:'''),
 ("diag_no_action", '''        diag["action"] = (f"re-run the {gate} gate on {target}''', '''        diag["action"] = (f"re-run the gate on {target}'''),
 ("fixture_rev_untyped", '''            if key in data and not isinstance(data[key], str):
                return _invalid_packet(f"{key} must be a string")''', '''            pass'''),
 ("fixture_revs_dropped", '''            subject_revision=data.get("subject_revision"),
            verified_revision=data.get("verified_revision"),
        )''', '''        )'''),
 ("binding_key_always", '''        }, **({"revision_binding": binding} if binding else {})),''', '''        }, **({"revision_binding": binding} if binding or True else {})),'''),
]
