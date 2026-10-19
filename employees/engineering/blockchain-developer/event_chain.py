#!/usr/bin/env python3
"""Synthetic immutable-event log: append, verify and recover a local hash-chained JSON-lines file.

  event_chain.py append LOG --claimed-by NAME --body JSON [--at ISO-TIME]
  event_chain.py verify LOG [--anchor SEQ:HASH] [--json]
  event_chain.py recover LOG --out NEW [--anchor SEQ:HASH] [--json]

Each line is {"seq", "prev", "at", "claimed_by", "body", "hash"}; hash = sha256 of the canonical JSON of the
other five fields, prev = the previous event's hash (64 zeros for seq 0). This is a local integrity check,
not a blockchain: there is no wallet, key, signature, network or transaction.

What a pass means, and what it does not:
- every event up to the head hashes correctly and links to the one before it, in sequence;
- without --anchor the chain is only self-consistent: whoever can write the file can rewrite all of it. An
  anchor (a seq:hash recorded somewhere the writer cannot change) is what detects a rewrite or truncation;
- claimed_by is plain text. It is reported as claimed, never as an authenticated identity.

Exit codes: 0 verified (recover: the verified prefix was written); 1 findings (recover: nothing verified to
write); 2 invalid use or unreadable input (nothing written); 4 another appender holds the lock.
Python 3.9+, standard library, POSIX (fcntl lock for append). recover never modifies LOG.
"""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

GENESIS = "0" * 64
HEX = re.compile(r"^[0-9a-f]{64}$")
FIELDS = ("seq", "prev", "at", "claimed_by", "body")
MAX_LINE = 1 << 20


class Invalid(Exception):
    pass


def canon(o):
    return json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_hash(e):
    return hashlib.sha256(canon({k: e[k] for k in FIELDS}).encode("utf-8")).hexdigest()


def _time(v):
    if not isinstance(v, str):
        return None
    try:
        t = dt.datetime.fromisoformat(v)
    except ValueError:
        return None
    return t if t.tzinfo is not None else None


def parse_anchor(s):
    if s is None:
        return None
    m = re.match(r"^(\d{1,12}):([0-9a-f]{64})$", s)
    if not m:
        raise Invalid("--anchor must be SEQ:SHA256 (64 lowercase hex)")
    return int(m.group(1)), m.group(2)


def verify(raw, anchor=None):
    """Pure check of the log bytes. Stops trusting at the first break; later lines are counted, not used."""
    F, good, prev, prev_t = [], [], GENESIS, None
    lines = raw.split(b"\n")
    tail_torn = bool(raw) and not raw.endswith(b"\n")
    if lines and lines[-1] == b"":
        lines = lines[:-1]
    broken = False
    for n, line in enumerate(lines, 1):
        if broken:
            break
        where = "line %d" % n
        if len(line) > MAX_LINE:
            F.append({"code": "line_too_long", "at": where}); broken = True; continue
        try:
            e = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            code = "torn_tail" if (tail_torn and n == len(lines)) else "line_not_json"
            F.append({"code": code, "at": where}); broken = True; continue
        if not isinstance(e, dict) or set(e) != set(FIELDS) | {"hash"}:
            F.append({"code": "fields_wrong", "at": where, "detail": "need exactly %s and hash" % ", ".join(FIELDS)}); broken = True; continue
        if type(e["seq"]) is not int or not isinstance(e["claimed_by"], str) or not e["claimed_by"].strip() \
                or not isinstance(e["body"], dict) or not isinstance(e["prev"], str) or not isinstance(e["hash"], str):
            F.append({"code": "fields_wrong", "at": where, "detail": "seq int, claimed_by text, body object, prev and hash text"}); broken = True; continue
        t = _time(e["at"])
        if t is None:
            F.append({"code": "time_invalid", "at": where, "detail": "at must be an ISO time with offset"}); broken = True; continue
        if e["seq"] != len(good):
            F.append({"code": "seq_gap" if e["seq"] > len(good) else "seq_repeat", "at": where,
                      "detail": "expected seq %d, found %d" % (len(good), e["seq"])}); broken = True; continue
        if e["prev"] != prev:
            F.append({"code": "broken_link", "at": where, "detail": "prev does not match the hash of seq %d" % (len(good) - 1)}); broken = True; continue
        if event_hash(e) != e["hash"]:
            F.append({"code": "hash_mismatch", "at": where, "detail": "content of seq %d was changed after it was written" % e["seq"]}); broken = True; continue
        if prev_t is not None and t < prev_t:
            F.append({"code": "time_regression", "at": where, "detail": "at is earlier than seq %d" % (len(good) - 1)}); broken = True; continue
        good.append(e); prev, prev_t = e["hash"], t
    unverified = len(lines) - len(good)
    anchor_state = "none (self-consistent only)"
    if anchor is not None:
        a_seq, a_hash = anchor
        if a_seq >= len(good):
            F.append({"code": "anchor_not_reached", "detail": "anchored seq %d is beyond the last verified event (%d)" % (a_seq, len(good) - 1)})
            anchor_state = "not reached"
        elif good[a_seq]["hash"] != a_hash:
            F.append({"code": "anchor_mismatch", "detail": "seq %d hash differs from the anchor: the history up to it was rewritten" % a_seq})
            anchor_state = "mismatch"
        else:
            anchor_state = "matches seq %d" % a_seq
    if not lines:
        F.append({"code": "chain_empty"})
    claimed = {}
    for e in good:
        claimed[e["claimed_by"].strip()] = claimed.get(e["claimed_by"].strip(), 0) + 1
    return {"schema": "solaris.event-chain-report/1", "result": "verified" if not F else "findings",
            "events_total": len(lines), "verified": len(good), "unverified_after_break": unverified,
            "head": {"seq": len(good) - 1, "hash": prev} if good else None, "anchor": anchor_state,
            "claimed_by": {"counts": dict(sorted(claimed.items())), "identity": "claimed in plain text, not authenticated"},
            "findings": F, "statement": "local hash-chain integrity only; no signature, wallet, transaction or legal effect"}, good


def _atomic(path, data):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix="." + path.name + ".")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, str(path))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append(log, claimed_by, body_s, at=None):
    try:
        body = json.loads(body_s)
    except ValueError:
        raise Invalid("--body must be a JSON object")
    if not isinstance(body, dict):
        raise Invalid("--body must be a JSON object")
    if not isinstance(claimed_by, str) or not claimed_by.strip():
        raise Invalid("--claimed-by is required (it is recorded as a claim, not checked)")
    at = at or dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds")
    if _time(at) is None:
        raise Invalid("--at must be an ISO time with offset")
    log = Path(log)
    # inputs are validated above, before the log is opened or created
    fd = os.open(str(log), os.O_RDWR | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            # wait briefly for another appender, then give up without writing
            import time
            for _ in range(200):
                time.sleep(0.01)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB); break
                except OSError:
                    continue
            else:
                return 4, None
        raw = log.read_bytes()
        rep, good = verify(raw)
        if rep["findings"] and not (rep["findings"] == [{"code": "chain_empty"}]):
            raise Invalid("the log does not verify (%s); recover it to a new file before appending" % rep["findings"][0]["code"])
        prev = good[-1]["hash"] if good else GENESIS
        if good and _time(at) < _time(good[-1]["at"]):
            at = good[-1]["at"]  # keep time monotonic under clock skew between appenders
        e = {"seq": len(good), "prev": prev, "at": at, "claimed_by": claimed_by.strip(), "body": body}
        e["hash"] = event_hash(e)
        os.write(fd, (canon(e) + "\n").encode("utf-8")); os.fsync(fd)
        return 0, e
    finally:
        os.close(fd)


def render(r):
    out = ["event chain: %s; %d of %d event(s) verified; anchor %s" % (r["result"], r["verified"], r["events_total"], r["anchor"])]
    if r["head"]:
        out.append("head: seq %d %s" % (r["head"]["seq"], r["head"]["hash"]))
    for f in r["findings"]:
        out.append("  FINDING %s%s%s" % (f["code"], " at " + f["at"] if f.get("at") else "", ": " + f["detail"] if f.get("detail") else ""))
    out.append("claimed_by (not authenticated): " + ", ".join("%s %d" % kv for kv in r["claimed_by"]["counts"].items()))
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="local hash-chained event log")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append"); a.add_argument("log"); a.add_argument("--claimed-by", required=True); a.add_argument("--body", required=True); a.add_argument("--at")
    v = sub.add_parser("verify"); v.add_argument("log"); v.add_argument("--anchor"); v.add_argument("--json", action="store_true")
    r = sub.add_parser("recover"); r.add_argument("log"); r.add_argument("--out", required=True); r.add_argument("--anchor"); r.add_argument("--json", action="store_true")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "append":
            rc, e = append(ns.log, ns.claimed_by, ns.body, ns.at)
            if rc == 4:
                print("another appender holds the lock; nothing written", file=sys.stderr); return 4
            print("appended seq %d %s" % (e["seq"], e["hash"])); return 0
        anchor = parse_anchor(ns.anchor)
        try:
            raw = Path(ns.log).read_bytes()
        except OSError as ex:
            raise Invalid("log unreadable: %s" % (ex.strerror or ex.__class__.__name__))
        rep, good = verify(raw, anchor)
        if ns.cmd == "recover":
            out = Path(ns.out)
            if out.exists() and out.resolve() == Path(ns.log).resolve():
                raise Invalid("--out must be a new file; recover never rewrites the log in place")
            if out.exists():
                raise Invalid("--out already exists; choose a new file")
            keep = good
            if anchor is not None and rep["anchor"] == "mismatch":
                keep = good[:0]  # history before the anchor was rewritten: nothing here is trustworthy
            rep["recovered"] = {"kept": len(keep), "dropped": rep["events_total"] - len(keep), "out": out.name}
            if not keep:
                print(json.dumps(rep, indent=2) if ns.json else render(rep) + "\nnothing verified to recover; nothing written")
                return 1
            _atomic(out, "".join(canon(e) + "\n" for e in keep).encode("utf-8"))
            print(json.dumps(rep, indent=2) if ns.json else render(rep) + "\nrecovered %d event(s) to %s; %d dropped; the original log is unchanged"
                  % (len(keep), out.name, rep["recovered"]["dropped"]))
            return 0
        print(json.dumps(rep, indent=2) if ns.json else render(rep))
        return 0 if rep["result"] == "verified" else 1
    except Invalid as ex:
        print("invalid: %s. Nothing was written." % ex, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
