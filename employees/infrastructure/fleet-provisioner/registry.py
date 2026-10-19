#!/usr/bin/env python3
"""Offline fleet registration for synthetic machines: one registration per machine, one owner at a time (G07).

The registry is a folder (`--root`, default `$SOLARIS_FLEET_ROOT`) holding:

  registry.json  current machines: alias, machine_id, owner, owner_epoch, status (replaced atomically)
  ops.jsonl      append-only change log: intent, then commit or abort, per request id
  FLEET.md       roster view rendered from registry.json after every change (do not edit by hand)

A machine is identified by an identity file (JSON with a `machine_id`), not by the name a caller types.
Every change runs under an fcntl lock and carries a caller-chosen request id: repeating a request returns the
recorded result instead of applying it twice. Ownership changes are compare-and-set on the current owner and
owner_epoch, so a caller holding an older view of the owner is refused. A change writes its intent, replaces
registry.json, then writes its commit; a crash between those steps is settled by the next command (commit if
registry.json already holds the change, abort otherwise, so the prior owner stays). registry.json is bound by
hash to the last settled change, so an edit made outside this tool is refused instead of built upon.

`claim` (and handoff.py work orders with a `fleet` block, G04) admit work only for the registered machine
whose identity file matches, while it is active, for its current owner at its current owner_epoch.

Synthetic and local only: it never contacts, provisions or controls a real machine, and stores no secret.
Exit codes: 0 done (including a repeated request); 2 refused or invalid, nothing changed; 75 crash drill.
"""
import argparse
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SCHEMA = "solaris.fleet-registry/1"
ALIAS_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
MID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,63}$")
REQ_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$")
CRASH_EXIT = 75
FAIL_POINTS = ("before-replace", "after-replace")


class Refused(Exception):
    pass


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def atomic_write(path, data):
    fd, tmp = tempfile.mkstemp(prefix=".reg-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_identity(path):
    try:
        ident = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        raise Refused("identity file unreadable: %s" % path)
    mid = ident.get("machine_id") if isinstance(ident, dict) else None
    if not isinstance(mid, str) or not MID_RE.match(mid):
        raise Refused("identity file must hold machine_id: 8-64 letters, digits or dashes")
    return mid


def check_owner(owner):
    if not isinstance(owner, str) or not owner.strip() or len(owner) > 120 or "\n" in owner or "|" in owner:
        raise Refused("owner must name one accountable person or role (1-120 characters, no | or newline)")
    return owner.strip()


class Registry:
    """Open under the lock; settles an unfinished change before anything else reads the state."""

    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_dir():
            raise Refused("registry root does not exist: %s" % root)
        self.reg_p, self.ops_p = self.root / "registry.json", self.root / "ops.jsonl"
        self.lock_fd = os.open(str(self.root / ".registry.lock"), os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(self.lock_fd, fcntl.LOCK_EX)
        self.notes = []
        self._load_ops()
        self._load_state()
        self._settle()

    def close(self):
        os.close(self.lock_fd)

    def _load_ops(self):
        self.ops = []
        data = self.ops_p.read_bytes() if self.ops_p.exists() else b""
        if data and not data.endswith(b"\n"):
            cut = data.rfind(b"\n") + 1
            with open(self.ops_p, "r+b") as f:
                f.truncate(cut)
            data = data[:cut]
            self.notes.append("ops log had a torn last line (crash mid-write); it was cut")
        for n, line in enumerate(data.splitlines(), 1):
            try:
                rec = json.loads(line.decode("utf-8"))
                if not isinstance(rec, dict) or rec.get("phase") not in ("intent", "commit", "abort"):
                    raise ValueError
            except (ValueError, UnicodeDecodeError):
                raise Refused("ops log line %d is unreadable; inspect %s before changing the fleet" % (n, self.ops_p))
            self.ops.append(rec)

    def _load_state(self):
        if not self.reg_p.exists():
            self.state, self.state_sha = {"schema": SCHEMA, "seq": 0, "last_op": None, "machines": []}, None
            return
        raw = self.reg_p.read_bytes()
        try:
            st = json.loads(raw.decode("utf-8"))
            if not isinstance(st, dict) or st.get("schema") != SCHEMA or not isinstance(st.get("machines"), list):
                raise ValueError
        except (ValueError, UnicodeDecodeError):
            raise Refused("registry.json is not a fleet registry; inspect it before changing the fleet")
        self.state, self.state_sha = st, sha(raw)

    def _append(self, rec):
        with open(self.ops_p, "ab") as f:
            f.write((canon(rec) + "\n").encode("utf-8"))
            f.flush()
            os.fsync(f.fileno())
        self.ops.append(rec)

    def _settle(self):
        open_intent, settled_sha = None, None
        for rec in self.ops:
            if rec["phase"] == "intent":
                open_intent = rec
            else:
                if rec["phase"] == "commit":
                    settled_sha = rec.get("state_sha256")
                open_intent = None
        if open_intent:
            if self.state_sha == open_intent.get("state_sha256"):
                self._append({"phase": "commit", "request_id": open_intent["request_id"],
                              "state_sha256": self.state_sha, "result": open_intent.get("result"),
                              "recovered": True})
                settled_sha = self.state_sha
                self.notes.append("finished change %s interrupted after registry.json was replaced"
                                  % open_intent["request_id"])
            else:
                self._append({"phase": "abort", "request_id": open_intent["request_id"], "recovered": True})
                self.notes.append("rolled back change %s interrupted before registry.json was replaced; prior "
                                  "state kept" % open_intent["request_id"])
            self.render()
        if self.state_sha != settled_sha:
            raise Refused("registry.json does not match the last recorded change (edited outside registry.py?); "
                          "nothing changed")

    def find(self, alias=None, machine_id=None):
        for m in self.state["machines"]:
            if (alias is not None and m["alias"] == alias) or (machine_id is not None and m["machine_id"] == machine_id
                                                               and m["status"] == "active"):
                return m
        return None

    def prior(self, request_id, args):
        for rec in self.ops:
            if rec.get("request_id") == request_id and rec["phase"] == "intent":
                if rec.get("args_sha256") != sha(canon(args).encode()):
                    raise Refused("request id %s was already used for a different change" % request_id)
        for rec in reversed(self.ops):
            if rec.get("request_id") == request_id and rec["phase"] == "commit":
                return rec.get("result")
        return None

    def apply(self, request_id, args, new_state, result, fail_at=None):
        body = dict(new_state, seq=self.state["seq"] + 1, last_op=request_id)
        raw = (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
        self._append({"phase": "intent", "request_id": request_id, "args_sha256": sha(canon(args).encode()),
                      "state_sha256": sha(raw), "result": result})
        if fail_at == "before-replace":
            os._exit(CRASH_EXIT)
        atomic_write(self.reg_p, raw)
        if fail_at == "after-replace":
            os._exit(CRASH_EXIT)
        self._append({"phase": "commit", "request_id": request_id, "state_sha256": sha(raw), "result": result})
        self.state, self.state_sha = body, sha(raw)
        self.render()
        return result

    def render(self):
        lines = ["# FLEET (rendered from registry.json by registry.py; do not edit by hand)", "",
                 "| alias | machine_id | owner | owner_epoch | status |", "|---|---|---|---|---|"]
        for m in sorted(self.state["machines"], key=lambda m: m["alias"]):
            lines.append("| %s | %s | %s | %d | %s |" % (m["alias"], m["machine_id"], m["owner"], m["owner_epoch"],
                                                     m["status"]))
        atomic_write(self.root / "FLEET.md", ("\n".join(lines) + "\n").encode("utf-8"))


def _copy(state):
    return json.loads(canon(state))


def change(reg, kind, a, fail_at=None):
    req = a["request_id"]
    if not isinstance(req, str) or not REQ_RE.match(req):
        raise Refused("--request-id must be 1-80 letters, digits or . _ : -")
    if not isinstance(a.get("alias"), str) or not ALIAS_RE.match(a["alias"]):
        raise Refused("alias must be 1-40 lowercase letters, digits or dashes")
    args = dict(a, kind=kind)
    done = reg.prior(req, args)
    if done is not None:
        return dict(done, repeated=True)
    st, m = _copy(reg.state), reg.find(alias=a["alias"])
    if kind == "register":
        same = reg.find(machine_id=a["machine_id"])
        if same and same["alias"] != a["alias"]:
            raise Refused("machine %s is already registered as %s; one registration per machine"
                          % (a["machine_id"], same["alias"]))
        if m and m["machine_id"] != a["machine_id"]:
            raise Refused("alias %s belongs to another machine" % a["alias"])
        if m and m["status"] != "active":
            raise Refused("alias %s is retired; register the machine under a new alias" % a["alias"])
        if m:
            if m["owner"] != a["owner"]:
                raise Refused("%s is already registered to %s; change owners with transfer" % (m["alias"], m["owner"]))
            return {"alias": m["alias"], "owner": m["owner"], "owner_epoch": m["owner_epoch"], "change": "none"}
        st["machines"].append({"alias": a["alias"], "machine_id": a["machine_id"], "owner": a["owner"],
                               "owner_epoch": 1, "status": "active", "registered_by": req})
        res = {"alias": a["alias"], "owner": a["owner"], "owner_epoch": 1, "change": "registered"}
    else:
        if not m:
            raise Refused("no machine registered as %s" % a["alias"])
        if m["status"] != "active":
            raise Refused("%s is retired" % m["alias"])
        if m["owner"] != a["from_owner"] or m["owner_epoch"] != a["expect_epoch"]:
            raise Refused("stale owner: %s is owned by %s at epoch %d, not %s at epoch %s"
                          % (m["alias"], m["owner"], m["owner_epoch"], a["from_owner"], a["expect_epoch"]))
        t = [x for x in st["machines"] if x["alias"] == a["alias"]][0]
        t["owner_epoch"] += 1
        if kind == "transfer":
            t["owner"] = a["to_owner"]
        else:
            t["status"] = "retired"
        res = {"alias": t["alias"], "owner": t["owner"], "owner_epoch": t["owner_epoch"],
               "change": "transferred" if kind == "transfer" else "retired"}
    return reg.apply(req, args, st, res, fail_at)


def check_claim(root, alias, identity_path, owner, epoch):
    """Return the machine record if this machine may take work for owner at epoch; raise Refused otherwise."""
    reg = Registry(root)
    try:
        mid = read_identity(identity_path)
        m = reg.find(alias=alias)
        if not m:
            raise Refused("no machine registered as %s" % alias)
        if m["machine_id"] != mid:
            raise Refused("wrong machine: this identity is not the machine registered as %s" % alias)
        if m["status"] != "active":
            raise Refused("%s is retired and cannot take work" % alias)
        if m["owner"] != owner or m["owner_epoch"] != epoch:
            raise Refused("stale owner: %s is owned by %s at epoch %d, not %s at epoch %s"
                          % (alias, m["owner"], m["owner_epoch"], owner, epoch))
        return dict(m)
    finally:
        reg.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline fleet registration (see the module docstring).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    cmds = {n: sub.add_parser(n) for n in ("register", "transfer", "retire", "claim", "status")}
    for p in cmds.values():
        p.add_argument("--root", default=os.environ.get("SOLARIS_FLEET_ROOT"))
    for n in ("register", "transfer", "retire", "claim"):
        cmds[n].add_argument("--alias", required=True)
    for n in ("register", "transfer", "retire"):
        cmds[n].add_argument("--request-id", required=True)
        cmds[n].add_argument("--fail-at", choices=FAIL_POINTS, help="crash drill")
    for n in ("register", "claim"):
        cmds[n].add_argument("--identity", required=True)
        cmds[n].add_argument("--owner", required=True)
    for n in ("transfer", "retire"):
        cmds[n].add_argument("--from-owner", required=True)
        cmds[n].add_argument("--expect-epoch", type=int, required=True)
    cmds["transfer"].add_argument("--to-owner", required=True)
    cmds["claim"].add_argument("--epoch", type=int, required=True)
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0
    try:
        if not a.root:
            raise Refused("--root or SOLARIS_FLEET_ROOT is required")
        if a.cmd == "claim":
            m = check_claim(a.root, a.alias, a.identity, check_owner(a.owner), a.epoch)
            out = {"claim": "admitted", "alias": m["alias"], "owner": m["owner"], "owner_epoch": m["owner_epoch"]}
        else:
            reg = Registry(a.root)
            try:
                if a.cmd == "status":
                    out = {"machines": reg.state["machines"], "seq": reg.state["seq"]}
                else:
                    args = {"request_id": a.request_id, "alias": a.alias}
                    if a.cmd == "register":
                        args.update(machine_id=read_identity(a.identity), owner=check_owner(a.owner))
                    else:
                        args.update(from_owner=check_owner(a.from_owner), expect_epoch=a.expect_epoch)
                        if a.cmd == "transfer":
                            args["to_owner"] = check_owner(a.to_owner)
                            if args["to_owner"] == args["from_owner"]:
                                raise Refused("transfer needs a different owner")
                    out = change(reg, a.cmd, args, a.fail_at)
                out["notes"] = reg.notes
            finally:
                reg.close()
    except Refused as e:
        sys.stderr.write("refused: %s\n" % e)
        return 2
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
