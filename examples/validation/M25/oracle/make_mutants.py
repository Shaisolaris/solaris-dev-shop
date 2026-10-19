"""M25 mutants of device_protocol.py (Grok self-validation). One exact single-occurrence replacement each;
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
 "window_le": ['if s - d["next"] < WINDOW and len(d["buffer"]) < WINDOW:', 'if s - d["next"] <= WINDOW and len(d["buffer"]) <= WINDOW:'],
 "window_unbounded": ['if s - d["next"] < WINDOW and len(d["buffer"]) < WINDOW:', 'if True:'],
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
