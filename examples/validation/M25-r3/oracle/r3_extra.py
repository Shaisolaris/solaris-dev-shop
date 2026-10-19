R3 = {
 "r2_body_hash_off": ['    if st.get("body_sha256") != _body_sha(st):\n', '    if False:\n'],
 "r3g_hash_snap_only": ['rest = {k: v for k, v in body.items() if k != "body_sha256"}', 'rest = {k: v for k, v in body.items() if k in ("devices", "claims", "counts", "anomalies")}'],
 "r3g_hash_no_lines": ['rest = {k: v for k, v in body.items() if k != "body_sha256"}', 'rest = {k: v for k, v in body.items() if k not in ("body_sha256", "lines")}'],
 "r3g_nonobj_as_invalid": ['raise Damaged(f"state: {spath.name} is not a checkpoint object', 'raise Invalid(f"state: {spath.name} is not a checkpoint object'],
 "r3g_recount_off": ['if st["lines"] != prefix.count(b"\\n") + (1 if prefix and not prefix.endswith(b"\\n") else 0):', 'if False:'],
 "r3g_recount_no_tail": [' + (1 if prefix and not prefix.endswith(b"\\n") else 0):', ':'],
 "r3g_parent_walk_off": ['            if not parent.is_dir():\n                raise Invalid(f"--record: {parent} is not a folder', '            if False:\n                raise Invalid(f"--record: {parent} is not a folder'],
 "r3g_parent_no_symlink": ['if parent.exists() or parent.is_symlink():', 'if parent.exists():'],
 "r3g_parent_first_only": ['                raise Invalid(f"--record: {parent} is not a folder, so {rec} cannot be created")\n            break\n', '                raise Invalid(f"--record: {parent} is not a folder, so {rec} cannot be created")\n            break\n        break\n'],
 "r3g_oserror_uncaught": ['        except OSError as exc:\n            raise Invalid(f"--record: cannot write', '        except ZeroDivisionError as exc:\n            raise Invalid(f"--record: cannot write'],
 "r3g_schema_old": ['STATE_SCHEMA = "solaris.device-protocol-state/3"', 'STATE_SCHEMA = "solaris.device-protocol-state/2"'],
}
