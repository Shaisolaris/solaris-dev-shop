"""M25 r2 mutants of device_protocol.py at a902bc4 (Grok self-validation). r1 set with window_le and window_unbounded
re-pointed to the r2 boundary line (window_le keeps its r1 meaning: widen the window by one), plus r2 mutants (r2_*). One exact single-occurrence replacement each;
the generator asserts count == 1. Names ending _EQUIV are expected-equivalent controls (reason in comment).
Usage: make_mutants.py SRC NAME OUT | make_mutants.py --list"""
import sys
from pathlib import Path
M = {
 "no_claim_dedupe": ['if e["cmd"] in self.claimed or e["cmd"] in d["acked"]:', 'if False:'],
 "claimed_only_EQUIV": ['if e["cmd"] in self.claimed or e["cmd"] in d["acked"]:', 'if e["cmd"] in d["acked"]:'],  # claims come only from the addressed device, so claimed is a subset of that device's acked, which survives reboots
 "acked_only_claimed": ['if e["cmd"] in self.claimed or e["cmd"] in d["acked"]:', 'if e["cmd"] in self.claimed:'],
 "stale_applied": ['        elif e["boot"] < d["boot"]:\n', '        elif False:\n'],
 "dup_seq_reapplied": ['if s < d["next"] or s in d["buffer"]:', 'if s in d["buffer"]:'],
 "window_le": ['if s - d["next"] <= WINDOW and len(d["buffer"]) < WINDOW:', 'if s - d["next"] <= WINDOW + 1 and len(d["buffer"]) <= WINDOW:'],
 "window_unbounded": ['if s - d["next"] <= WINDOW and len(d["buffer"]) < WINDOW:', 'if True:'],
 "r2_window_r1_revert": ['if s - d["next"] <= WINDOW and', 'if s - d["next"] < WINDOW and'],
 "r2_body_hash_off": ['    if st.get("body_sha256") != _body_sha(snap):\n', '    if False:\n'],
 "r2_claim_ack_check_off": ['        if cmds.get(c["cmd"]) != c or c["cmd"] not in devs.get(c["device"], {}).get("acked", []):\n', '        if cmds.get(c["cmd"]) != c:\n'],
 "r2_ack_owner_off": ['cmds.get(c, {}).get("device") != name for c in d["acked"]', 'False for c in d["acked"]'],
 "r2_buffer_window_off": ['or e["device"] != name or not d["next"] < e["seq"] <= d["next"] + WINDOW:', 'or e["device"] != name:'],
 "r2_applied_ge_off": ['    if counts.get("applied", 0) < len(claims):\n', '    if False:\n'],
 "r2_counts_check_off": ['any(not isinstance(k, str) or not _int(v, 0, 2 ** 62) for k, v in counts.items())', 'False'],
 "r2_damaged_exit2": ['        return 4\n', '        return 2\n'],
 "r2_record_symlink_ok": ['if rec and (rec.is_symlink() or (rec.exists() and not rec.is_dir())):', 'if rec and (rec.exists() and not rec.is_dir()):'],
 "r2_record_no_mkdir": ['        rec.mkdir(parents=True, exist_ok=True)', '        pass'],
 "r2_device_match": ['not DEVICE_RE.fullmatch(e["device"])', 'not re.match(r"^[a-z0-9][a-z0-9-]{0,63}$", e["device"])'],
 "r2_cmdlog_match": ['or not CMD_RE.fullmatch(c["cmd"]) \\', 'or not re.match(r"^c-[0-9a-f]{1,32}$", c["cmd"]) \\'],
 "r2_ackcmd_match": ['not CMD_RE.fullmatch(e["cmd"])', 'not re.match(r"^c-[0-9a-f]{1,32}$", e["cmd"])'],
 "r2_snapshot_check_off": ['            why = why or check_snapshot(st, cmds)\n', '            why = why or None\n'],
 "no_device_match": ['if c is None or c["device"] != name:', 'if c is None:'],
 "no_state_match": ['            if e["state"] != want:\n', '            if False:\n'],
 "rejected_claims": ['            if e["result"] != "done":\n', '            if e["result"] == "never":\n'],
 "no_unexplained": ['            if e["state"] != d["state"]:\n', '            if False:\n'],
 "no_end_flush": ['self._flush(name, d, reason="end_of_input")', 'pass'],
 "bool_as_int": ['return isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi', 'return isinstance(v, int) and lo <= v <= hi'],
 "isfinite_off_EQUIV": [' or not math.isfinite(f) or ', ' or '],  # NaN and inf both fail 0 <= f <= 1000 anyway
 "unknown_field_ok": ['    if set(e) - allowed:\n        return "unknown_field"\n', ''],
 "max_devices_off": ['            if len(self.devices) >= MAX_DEVICES:\n', '            if False:\n'],
 "prefix_hash_off": [' or hashlib.sha256(prefix).hexdigest() != st.get("events_prefix_sha256")', ''],
 "commands_hash_off": [' or st.get("commands_sha256") != csha', ''],
 "dup_cmd_log_ok": ['        if c["cmd"] in cmds:\n', '        if False:\n'],
 "reboot_keeps_next": ['d["boot"], d["next"], d["buffer"] = e["boot"], 1, {}', 'd["boot"], d["buffer"] = e["boot"], {}'],
 "flush_no_gap_note": ['                self._note("gap", device=name', '                self._count("gap_quiet") if 0 else None; (lambda **k: None)(device=name'],
}
if sys.argv[1] == "--list":
    print(" ".join(M)); sys.exit(0)
src_path, name, out = sys.argv[1:4]
src = Path(src_path).read_text()
old, new = M[name]
assert src.count(old) == 1, (name, src.count(old))
Path(out).write_text(src.replace(old, new))
