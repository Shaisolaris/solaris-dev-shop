#!/usr/bin/env python3
"""delivery_evidence.py: evidence for a multi-specialist customer delivery (G39).

The delivery lead does not perform specialist work. This tool records that a specialist's existing tool
actually ran in the delivery folder (exit code, tool and output sha256), and later checks a delivery claim
against those records, the files on disk and the G04 work-order status:

  record ROOT --role DEPT/ROLE --outputs PATH... [--ok-exit 0,1] [--worker NAME] [--timeout S] -- CMD ARGS...
  verify ROOT --claims CLAIMS.json [--json] [--out FILE]

Records live in ROOT/.delivery/contributions.jsonl, one JSON object per line, each carrying the sha256 of
the previous line, and .delivery/head.json holds the sha256 of the last one, so an edited, removed or replaced
record breaks the chain (self-consistency only: someone who rewrites every line and the head is not caught). A record is appended only after the
command has finished; a recorder killed earlier leaves no record and the step is simply run again.
Output digests come from the G05 assurance engine (artifact_digests) and are compared with binding_state,
so a changed output or a changed tool makes the contribution stale and names the command to re-run.

Exit codes: record 0 ok, 1 recorded but not ok, 2 invalid input (nothing appended), 3 ledger does not
verify (nothing appended), 4 ledger lock held. verify 0 GO, 1 NO_GO, 2 invalid input.

Records are evidence that a command ran here with that exit code and produced these bytes. They do not
show that the output is correct beyond each tool's own checks, and --worker is a plain-text claim.
"""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
QOS = REPO / "employees" / "quality-security" / "assurance" / "quality_os.py"
HANDOFF = REPO / "employees" / "infrastructure" / "fleet-dispatcher" / "handoff.py"
LEDGER_DIR = ".delivery"
LEDGER = "contributions.jsonl"
HEAD = "head.json"  # sha256 of the last record, so the last record cannot be edited unnoticed either
GENESIS = "0" * 64
ROLE_RE = re.compile(r"^[a-z][a-z0-9-]*/[a-z0-9][a-z0-9-]*$")
TOKEN_RE = re.compile(r"ghp_[A-Za-z0-9]{20,}|github[_]pat_|gho_[A-Za-z0-9]{20,}|\bsk-[A-Za-z0-9]{20,}|xox[abp]-|"
                      r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY")
MAX_LINE = 1 << 20
MAX_TIMEOUT = 3600
STEPS = ("activate", "brief", "deliver")
LIMITS = ("records show that a command ran in this folder with that exit code and produced these bytes; "
          "correctness beyond each tool's own checks is not shown; worker names are plain-text claims")


class Invalid(Exception):
    pass


class LedgerBroken(Exception):
    pass


def _load_qos():
    """Load the G05 engine by path without leaving a bytecode cache next to it."""
    spec = importlib.util.spec_from_file_location("solaris_quality_os_g39", str(QOS))
    if spec.name in sys.modules:
        return sys.modules[spec.name]
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses in the engine look their module up here
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    finally:
        sys.dont_write_bytecode = keep
    return mod


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _sha_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _root(raw):
    root = Path(raw)
    if not root.is_dir() or root.is_symlink():
        raise Invalid("ROOT must be an existing folder (not a symlink)")
    return root


def read_ledger(root):
    """Return (records, good_byte_length, torn_tail). Raises LedgerBroken on an edited or reordered record."""
    p = root / LEDGER_DIR / LEDGER
    if not p.exists():
        return [], 0, False
    if p.is_symlink() or not p.is_file():
        raise LedgerBroken("the ledger is not a regular file")
    raw = p.read_bytes()
    lines = raw.split(b"\n")
    tail = lines.pop()  # bytes after the last newline: empty when the file ends cleanly
    recs, prev, good = [], GENESIS, 0
    for n, line in enumerate(lines, 1):
        if len(line) > MAX_LINE:
            raise LedgerBroken("line %d is too long" % n)
        try:
            r = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            raise LedgerBroken("line %d is not JSON" % n)
        if not isinstance(r, dict) or r.get("prev") != prev or r.get("seq") != n - 1:
            raise LedgerBroken("line %d does not follow line %d (edited, removed or reordered record)" % (n, n - 1))
        prev = hashlib.sha256(line).hexdigest()
        good += len(line) + 1
        recs.append(r)
    hp = root / LEDGER_DIR / HEAD
    if recs:
        try:
            head = json.loads(hp.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            raise LedgerBroken("head.json is missing or unreadable while records exist")
        last_seq = len(recs) - 1
        # the head may lag by one record when an append was cut short between the line and the head write
        lag_ok = last_seq >= 1 and head == {"seq": last_seq - 1, "sha256": recs[-1]["prev"]}
        if head != {"seq": last_seq, "sha256": prev} and not lag_ok:
            raise LedgerBroken("the last record does not match head.json (edited or replaced record)")
    torn = bool(tail)
    if torn:
        try:
            json.loads(tail.decode("utf-8"))
            raise LedgerBroken("the last record has no newline but parses; it was written by something else")
        except (UnicodeDecodeError, ValueError):
            pass  # an append cut short: never committed, ignored
    return recs, good, torn


def _role_ok(role):
    if not isinstance(role, str) or not ROLE_RE.match(role):
        raise Invalid("--role must look like department/role, for example data/data-engineer")
    d = REPO / "employees" / role
    if not (d / "SKILL.md").is_file():
        raise Invalid("%s is not an employee in this repository (no employees/%s/SKILL.md)" % (role, role))


def _tool_digests(argv, root):
    """sha256 of every .py file named in the command, keyed repo:<path> or root:<path> so it can be
    re-checked later; a script elsewhere is keyed other:<name> and cannot be re-checked."""
    out = {}
    base = root.resolve()
    for a in argv:
        if not a.endswith(".py"):
            continue
        p = Path(a) if os.path.isabs(a) else (root / a)
        if not p.is_file():
            continue
        rp = p.resolve()
        if REPO in rp.parents:
            key = "repo:" + rp.relative_to(REPO).as_posix()
        elif base in rp.parents:
            key = "root:" + rp.relative_to(base).as_posix()
        else:
            key = "other:" + p.name
        out[key] = _sha_file(p)
    return out


def _tool_path(key, root):
    kind, _, rel = key.partition(":")
    return {"repo": REPO, "root": root.resolve()}.get(kind, None), rel


def cmd_record(ns):
    root = _root(ns.root)
    _role_ok(ns.role)
    argv = list(ns.cmd)
    if not argv:
        raise Invalid("give the specialist command after --")
    if any(TOKEN_RE.search(a) for a in argv):
        raise Invalid("a credential-shaped value is in the command; it is never recorded")
    if not ns.outputs:
        raise Invalid("--outputs is required: name the files the specialist produces")
    for o in ns.outputs:
        if os.path.isabs(o) or ".." in Path(o).parts or Path(o).parts[:1] == (LEDGER_DIR,):
            raise Invalid("output %r must be a relative path inside ROOT and outside %s" % (o[:80], LEDGER_DIR))
    try:
        ok_exit = sorted({int(x) for x in ns.ok_exit.split(",")})
    except ValueError:
        raise Invalid("--ok-exit must be comma-separated integers")
    if not (0 < ns.timeout <= MAX_TIMEOUT):
        raise Invalid("--timeout must be between 0 and %d seconds" % MAX_TIMEOUT)
    d = root / LEDGER_DIR
    if d.is_symlink():
        raise Invalid("%s must not be a symlink" % LEDGER_DIR)
    (d / "logs").mkdir(parents=True, exist_ok=True)
    read_ledger(root)  # refuse early on a broken ledger, before running anything
    log = d / "logs" / ("%s.log" % uuid.uuid4().hex)
    started = _now()
    with open(log, "wb") as lf:
        try:
            rc = subprocess.run(argv, cwd=str(root), stdout=lf, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                timeout=ns.timeout).returncode
            why = None
        except subprocess.TimeoutExpired:
            rc, why = None, "timeout after %gs" % ns.timeout
        except OSError as e:
            rc, why = None, "could not start: %s" % type(e).__name__
    qos = _load_qos()
    outputs = {}
    try:
        outputs = qos.artifact_digests(root, ns.outputs)
    except ValueError as e:
        why = why or ("outputs: %s" % str(e)[:200])
    ok = why is None and rc in ok_exit
    rec = {"role": ns.role, "worker": ns.worker, "argv": argv, "ok_exit": ok_exit, "exit": rc, "ok": ok,
           "reason": why if why else (None if ok else "exit %s not in %s" % (rc, ok_exit)),
           "claimed_outputs": list(ns.outputs), "outputs": outputs, "tools": _tool_digests(argv, root),
           "log": log.relative_to(root).as_posix(), "log_sha256": _sha_file(log),
           "started": started, "ended": _now(), "worker_identity": "claimed in plain text, not authenticated"}
    lockp = d / "ledger.lock"
    fd = os.open(str(lockp), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB if ns.no_wait else fcntl.LOCK_EX)
        except OSError:
            print("ledger lock held by another recorder; nothing appended", file=sys.stderr)
            return 4
        recs, good, torn = read_ledger(root)
        p = d / LEDGER
        prev = GENESIS
        if recs:
            with open(p, "rb") as f:
                body = f.read(good)
            prev = hashlib.sha256(body[:-1].split(b"\n")[-1]).hexdigest()
        rec = dict({"seq": len(recs), "prev": prev}, **rec)
        if torn:
            rec["dropped_torn_tail"] = True
        line = json.dumps(rec, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
        with open(p, "ab") as f:
            if torn:
                f.truncate(good)  # the cut-short record was never committed
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        _atomic(d / HEAD, json.dumps({"seq": rec["seq"], "sha256": hashlib.sha256(line[:-1]).hexdigest()},
                                     sort_keys=True).encode("utf-8"))
    finally:
        os.close(fd)
    print("%s record %d: %s exit %s%s" % (ns.role, rec["seq"], "ok" if ok else "NOT OK", rc,
                                          "" if ok else " (%s)" % rec["reason"]))
    return 0 if ok else 1


def _load_claims(path, root):
    try:
        c = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as e:
        raise Invalid("claims file unreadable: %s" % type(e).__name__)
    if not isinstance(c, dict) or c.get("schema") != "solaris.delivery-claims/1":
        raise Invalid('claims must be an object with "schema": "solaris.delivery-claims/1"')
    contribs = c.get("contributions")
    if not isinstance(contribs, list) or not contribs:
        raise Invalid("claims.contributions must be a non-empty list")
    seen = set()
    for x in contribs:
        if not isinstance(x, dict) or not isinstance(x.get("outputs"), list) or not x["outputs"] or \
                not all(isinstance(o, str) and o for o in x["outputs"]):
            raise Invalid("each contribution needs a role and a non-empty outputs list")
        _role_ok(x.get("role"))
        if x["role"] in seen:
            raise Invalid("role %s is claimed twice" % x["role"])
        seen.add(x["role"])
    order = c.get("order")
    if order is not None and (not isinstance(order, str) or os.path.isabs(order) or ".." in Path(order).parts
                              or not (root / order).is_file()):
        raise Invalid("claims.order must name a work order file inside ROOT")
    return c


def _contribution(qos, root, claim, recs):
    role, want = claim["role"], claim["outputs"]
    mine = [r for r in recs if r.get("role") == role]
    out = {"role": role, "outputs": want}
    if not mine:
        out.update(state="unevidenced", action="run the %s tool through delivery_evidence.py record" % role)
        return out
    r = mine[-1]
    out.update(record=r["seq"], worker=r.get("worker"), exit=r.get("exit"), argv=r.get("argv"))
    if not r.get("ok"):
        out.update(state="failed", reason=r.get("reason"), action="fix the cause and re-run: %s" % " ".join(r["argv"]))
        return out
    recorded = r.get("outputs") or {}
    try:
        current = qos.artifact_digests(root, want)
    except ValueError as e:
        out.update(state="stale", reason="output no longer readable: %s" % str(e)[:200],
                   action="re-run: %s" % " ".join(r["argv"]))
        return out
    uncovered = sorted(p for p in current if p not in recorded)
    if uncovered:
        out.update(state="not_covered", not_recorded=uncovered[:20],
                   action="the record does not cover these files; re-run with them in --outputs")
        return out
    state, detail = qos.binding_state({"digests": {p: recorded[p] for p in current}}, {"digests": current})
    if state not in ("carried_forward", "current"):
        out.update(state="stale", changed=detail.get("changed", []), action="re-run: %s" % " ".join(r["argv"]))
        return out
    drift = []
    for key, h in sorted((r.get("tools") or {}).items()):
        base, rel = _tool_path(key, root)
        if base is None:
            continue
        p = base / rel
        if not p.is_file() or _sha_file(p) != h:
            drift.append(key)
    if drift:
        out.update(state="stale", tool_changed=drift, action="tool source changed; re-run: %s" % " ".join(r["argv"]))
        return out
    out["state"] = "evidenced"
    return out


def _handoff(root, order):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    p = subprocess.run([sys.executable, str(HANDOFF), "status", order, "--json"], cwd=str(root),
                       capture_output=True, text=True, timeout=120, env=env)
    if p.returncode != 0:
        return {"state": "invalid", "reason": (p.stderr or p.stdout).strip()[:300]}
    try:
        s = json.loads(p.stdout)
    except ValueError:
        return {"state": "invalid", "reason": "status output is not JSON"}
    steps = s.get("steps") or {}
    workers = {k: v[len("done by "):] for k, v in steps.items() if isinstance(v, str) and v.startswith("done by ")}
    cur = [d for d in s.get("deliveries") or [] if d.get("revision") == s.get("revision")]
    out = {"order_id": s.get("order_id"), "revision": s.get("revision"), "owner": s.get("owner"),
           "steps": steps, "workers": workers, "deliveries_this_revision": len(cur),
           "interrupted": s.get("interrupted")}
    if set(workers) != set(STEPS):
        out.update(state="incomplete", action="resume the order: handoff.py run %s --worker NAME" % order)
    elif len(cur) != 1:
        out.update(state="delivery_count_wrong", action="exactly one delivery per revision is expected")
    else:
        out["state"] = "delivered"
    return out


def cmd_verify(ns):
    root = _root(ns.root)
    claims = _load_claims(ns.claims, root)
    qos = _load_qos()
    rep = {"schema": "solaris.delivery-verdict/1", "limits": LIMITS}
    try:
        recs, _, torn = read_ledger(root)
        rep["ledger"] = {"records": len(recs), "chain": "intact", "torn_tail_ignored": torn}
    except LedgerBroken as e:
        recs = []
        rep["ledger"] = {"chain": "broken", "reason": str(e)}
    rep["contributions"] = [_contribution(qos, root, c, recs) for c in claims["contributions"]]
    if rep["ledger"]["chain"] == "broken":
        for c in rep["contributions"]:
            c.update(state="unevidenced", action="the ledger does not verify; no record can be trusted")
    claimed = {c["role"] for c in claims["contributions"]}
    rep["unclaimed_records"] = sorted({r["role"] for r in recs if r.get("role") not in claimed})
    if claims.get("order"):
        rep["handoff"] = _handoff(root, claims["order"])
    blockers = [c["role"] for c in rep["contributions"] if c["state"] != "evidenced"]
    if "handoff" in rep and rep["handoff"]["state"] != "delivered":
        blockers.append("handoff")
    if rep["ledger"]["chain"] == "broken":
        blockers.append("ledger")
    rep["verdict"] = "NO_GO" if blockers else "GO"
    rep["blockers"] = blockers
    data = json.dumps(rep, indent=2, sort_keys=True) + "\n"
    if ns.out:
        _atomic(ns.out, data.encode("utf-8"))
    if ns.json:
        sys.stdout.write(data)
    else:
        print("delivery verdict: %s" % rep["verdict"])
        print("ledger: %s" % (rep["ledger"].get("reason") or "%d records, chain intact" % rep["ledger"]["records"]))
        for c in rep["contributions"]:
            print("  %-40s %s%s" % (c["role"], c["state"], "" if c["state"] == "evidenced" else "  -> " + c.get("action", "")))
        if "handoff" in rep:
            h = rep["handoff"]
            print("  %-40s %s %s" % ("handoff (G04 work order)", h["state"], h.get("workers", h.get("reason", ""))))
        print("limits: " + LIMITS)
    return 0 if rep["verdict"] == "GO" else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd_name", required=True)
    r = sub.add_parser("record", help="run one specialist command in ROOT and record its evidence")
    r.add_argument("root")
    r.add_argument("--role", required=True)
    r.add_argument("--outputs", nargs="+", required=True)
    r.add_argument("--ok-exit", default="0")
    r.add_argument("--worker", default="unnamed")
    r.add_argument("--timeout", type=float, default=600)
    r.add_argument("--no-wait", action="store_true", help="exit 4 instead of waiting for the ledger lock")
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = []
    if argv[:1] == ["record"]:
        if "--" not in argv:
            print("invalid: give the specialist command after --", file=sys.stderr)
            return 2
        i = argv.index("--")
        argv, cmd = argv[:i], argv[i + 1:]
    v = sub.add_parser("verify", help="check a delivery claim against records, files and the work order")
    v.add_argument("root")
    v.add_argument("--claims", required=True)
    v.add_argument("--json", action="store_true")
    v.add_argument("--out")
    ns = ap.parse_args(argv)
    ns.cmd = cmd
    try:
        return cmd_record(ns) if ns.cmd_name == "record" else cmd_verify(ns)
    except Invalid as e:
        print("invalid: %s" % e, file=sys.stderr)
        return 2
    except LedgerBroken as e:
        print("ledger does not verify, nothing appended: %s" % e, file=sys.stderr)
        return 3


if __name__ == "__main__":
    sys.exit(main())
