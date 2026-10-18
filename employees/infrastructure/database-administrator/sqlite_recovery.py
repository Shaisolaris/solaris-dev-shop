#!/usr/bin/env python3
"""Bounded local SQLite snapshot, verification, restore and crash recovery.

Stdlib only. For local or synthetic datasets: a dataset is one directory that holds
SQLite files (*.db, *.sqlite, *.sqlite3) next to other files. A snapshot is a plain
directory written by this tool: one copy per database plus manifest.json. There are
no archives, so no archive member can alias a path.

Commands (exit 0 ok, 1 failed/unhealthy/busy, 2 refused or invalid):
  snapshot DATASET --out SNAPDIR [--db NAME ...] [--lock-timeout S]
  verify   SNAPDIR [--expect NAME ...]
  health   DATASET --expect NAME ... [--snapshot SNAPDIR] [--lock-timeout S]
  restore  DATASET --snapshot SNAPDIR --confirm SNAPSHOT_ID [--dry-run] [--lock-timeout S]
  recover  DATASET [--dry-run]

Safety model
  * Restore needs explicit operator intent: --confirm must equal the snapshot id.
    Freshness is never inferred from row counts; the plan lists what differs and
    the current files are always kept as recoverable copies (NAME.pre-restore-ID-RUN).
  * Every write path (snapshot, restore, recover) holds an exclusive dataset lock
    (flock on .solaris-recovery.lock, released by the kernel if the process dies).
    Dry runs take no lock and write nothing. POSIX only.
  * The snapshot is fully verified (file types, sha256, integrity_check, per-table
    value digests) before the target is touched; staged copies are re-verified.
  * Swaps are journaled renames (.solaris-recovery.json). `recover` inspects the
    filesystem after a crash at any point and rolls forward when every staged copy
    verifies, otherwise rolls back to the original files. It never needs the
    snapshot and never deletes an original or a verified copy.
  * SQLite lock waits are bounded by --lock-timeout (default 5 s).
  * Values compared: every user table (including names like sqlitedata), schema SQL,
    user_version and application_id. Reads of live files are read-only; on SQLite builds
    that refuse a read-only open of a WAL database without -shm, a query_only connection
    is used instead, which may create an empty -wal and a -shm (the database is unchanged).
  * manifest sha256 values detect accidental damage; they do not authenticate.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import socket
import sqlite3
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

SNAP_SCHEMA = "solaris.sqlite-snapshot/1"
JOURNAL_SCHEMA = "solaris.sqlite-restore-journal/1"
MANIFEST = "manifest.json"
JOURNAL = ".solaris-recovery.json"
LOCK = ".solaris-recovery.lock"
DB_SUFFIXES = (".db", ".sqlite", ".sqlite3")
SIDECARS = ("-wal", "-shm", "-journal")
MAX_DATABASES = 64
DEFAULT_LOCK_TIMEOUT = 5.0
EXIT = {"ok": 0, "planned": 0, "nothing_to_do": 0, "failed": 1, "unhealthy": 1, "busy": 1,
        "needs_human": 1, "refused": 2, "invalid": 2}


class Refused(Exception):
    """A safety refusal; nothing was changed by the step that raised it."""

    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _lkind(path: Path) -> str:
    try:
        st = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return "missing"
    if stat.S_ISLNK(st.st_mode):
        return "symlink"
    if stat.S_ISDIR(st.st_mode):
        return "directory"
    if stat.S_ISREG(st.st_mode):
        return "file" if st.st_nlink == 1 else "hardlinked file"
    return "special file"


def _says(kind: str) -> str:
    return "does not exist" if kind == "missing" else f"is a {kind}"


def _simple_name(name: Any) -> bool:
    return (isinstance(name, str) and name not in ("", ".", "..") and "/" not in name and "\\" not in name
            and "\x00" not in name and not name.startswith(".") and len(name) <= 200)


def _is_db_name(name: str) -> bool:
    return _simple_name(name) and name.endswith(DB_SUFFIXES)


def _inside(a: Path, b: Path) -> bool:
    try:
        a.relative_to(b)
        return True
    except ValueError:
        return False


def _atomic_write(target: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    tmp = target.parent / f".{target.name}.{secrets.token_hex(8)}.tmp"
    fd = os.open(tmp, flags, 0o644)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if _lkind(target) not in ("missing", "file"):
            raise Refused("refused", f"{target.name} changed type; not replaced")
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _copy_exclusive(src: Path, dst: Path) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(dst, flags, 0o644)
    with os.fdopen(fd, "wb") as out, open(src, "rb") as inp:
        shutil.copyfileobj(inp, out, 1 << 20)
        out.flush()
        os.fsync(out.fileno())


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


# -- SQLite reading -----------------------------------------------------------------

def _open_ro(path: Path, immutable: bool, timeout: float = DEFAULT_LOCK_TIMEOUT) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + ("?mode=ro&immutable=1" if immutable else "?mode=ro")
    return sqlite3.connect(uri, uri=True, timeout=timeout, isolation_level=None)


def _wal_header(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            head = fh.read(20)
    except OSError:
        return False
    return len(head) == 20 and head.startswith(b"SQLite format 3\x00") and head[18] == 2 and head[19] == 2


def _open_live(path: Path, timeout: float = DEFAULT_LOCK_TIMEOUT) -> sqlite3.Connection:
    """Read a live database (one other processes may use) without writing to it.

    Normally a read-only open. Some SQLite builds (Apple's 3.54.0, the default python3 on
    macOS) refuse a read-only open of a WAL database whose -shm file does not exist yet
    (SQLITE_CANTOPEN). Only then this falls back to a normal connection with query_only=ON:
    the database file is not written, but SQLite may create an empty -wal and a -shm.
    """
    con = None
    try:
        con = _open_ro(path, immutable=False, timeout=timeout)
        con.execute("SELECT count(*) FROM sqlite_master").fetchone()
        return con
    except sqlite3.OperationalError as exc:
        if con is not None:
            con.close()
        shm = path.parent / (path.name + "-shm")
        if "unable to open" not in str(exc) or _lkind(shm) != "missing" or not _wal_header(path):
            raise
    con = sqlite3.connect(str(path), timeout=timeout, isolation_level=None)
    con.execute("PRAGMA query_only = ON")
    return con


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _digest(con: sqlite3.Connection) -> Dict[str, Any]:
    """Integrity result, schema digest and per-table row count + value digest."""
    integrity = [r[0] for r in con.execute("PRAGMA integrity_check").fetchall()]
    schema = con.execute("SELECT type, name, tbl_name, sql FROM sqlite_master ORDER BY type, name").fetchall()
    # Header values that migrations and apps set; a restore must bring them back too.
    schema.append(("header", "user_version", con.execute("PRAGMA user_version").fetchone()[0],
                   "application_id", con.execute("PRAGMA application_id").fetchone()[0]))
    tables: Dict[str, Dict[str, Any]] = {}
    # Only SQLite's own tables start with "sqlite_" (reserved, case-insensitive). "_" is a LIKE
    # wildcard, so it is escaped: user tables such as sqlitedata or SQLiteLog are compared too.
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' "
                               "AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\' ORDER BY name").fetchall():
        try:
            cur = con.execute(f"SELECT * FROM {_quote(name)} ORDER BY rowid")
        except sqlite3.OperationalError:
            ncols = len(con.execute(f"PRAGMA table_info({_quote(name)})").fetchall())
            cur = con.execute(f"SELECT * FROM {_quote(name)} ORDER BY " + ", ".join(str(i + 1) for i in range(ncols)))
        h, n = hashlib.sha256(), 0
        for row in cur:
            h.update(repr(row).encode("utf-8"))
            h.update(b"\n")
            n += 1
        tables[name] = {"rows": n, "digest": h.hexdigest()}
    return {"integrity": "ok" if integrity == ["ok"] else "; ".join(integrity[:3]),
            "schema_digest": hashlib.sha256(repr(schema).encode("utf-8")).hexdigest(), "tables": tables}


def _row_set(con: sqlite3.Connection, table: str) -> set:
    return {repr(r) for r in con.execute(f"SELECT * FROM {_quote(table)}")}


# -- dataset lock ---------------------------------------------------------------------
# An flock on .solaris-recovery.lock. The kernel drops it when the holder exits, so a
# killed run never leaves a lock that blocks `recover`. The file is removed on release;
# the inode check below makes a waiter that opened a removed file retry.

def _acquire_lock(dataset: Path) -> int:
    for _ in range(20):
        if _lkind(dataset / LOCK) not in ("missing", "file"):
            raise Refused("busy", f"{LOCK} exists but is not a regular file; nothing changed")
        fd = os.open(dataset / LOCK, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            raise Refused("busy", _lock_message(dataset)) from None
        try:
            same = os.fstat(fd).st_ino == os.lstat(dataset / LOCK).st_ino
        except FileNotFoundError:
            same = False
        if same:
            os.ftruncate(fd, 0)
            os.write(fd, json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "started": _now()}).encode())
            return fd
        os.close(fd)
    raise Refused("busy", f"could not settle {LOCK}; nothing changed")


def _lock_held(dataset: Path) -> bool:
    """Read-only check used by dry runs."""
    if _lkind(dataset / LOCK) == "missing":
        return False
    if _lkind(dataset / LOCK) != "file":
        return True
    fd = os.open(dataset / LOCK, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        return False
    except OSError:
        return True
    finally:
        os.close(fd)


def _lock_message(dataset: Path) -> str:
    holder = "unknown holder"
    try:
        info = json.loads((dataset / LOCK).read_text(encoding="utf-8"))
        holder = f"pid {info.get('pid')} on {info.get('host')} since {info.get('started')}"
    except (OSError, ValueError):
        pass
    return f"another recovery operation is running on this dataset ({holder}); nothing changed. Retry when it ends."


def _locked(dataset: Path, fn: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    fd = _acquire_lock(dataset)
    try:
        return fn()
    finally:
        try:
            os.unlink(dataset / LOCK)
        except OSError:
            pass
        os.close(fd)


def _result(status: str, **extra: Any) -> Dict[str, Any]:
    res = {"status": status, "exit_code": EXIT[status], "messages": []}
    res.update(extra)
    return res


def _dataset_dir(arg: str) -> Path:
    p = Path(arg).expanduser()
    p = p if p.is_absolute() else Path.cwd() / p
    kind = _lkind(p)
    if kind != "directory":
        raise Refused("invalid", f"dataset {p}: {_says(kind)}; expected a real directory (symlinks are not followed)")
    return p.resolve()


# -- snapshot -------------------------------------------------------------------------

def snapshot(dataset_arg: str, out_arg: str, dbs: Optional[List[str]] = None,
             lock_timeout: float = DEFAULT_LOCK_TIMEOUT) -> Dict[str, Any]:
    try:
        dataset = _dataset_dir(dataset_arg)
        out = Path(out_arg).expanduser()
        out = out if out.is_absolute() else Path.cwd() / out
        if _lkind(out) != "missing":
            raise Refused("refused", f"snapshot destination {out} already exists; choose a new path")
        make_parent = _lkind(out.parent) == "missing" and _lkind(out.parent.parent) == "directory"
        if _lkind(out.parent) != "directory" and not make_parent:
            raise Refused("refused", "snapshot destination parent must be a real directory "
                          "(one missing level such as snapshots/ is created; deeper paths are not)")
        out = (out.parent.parent.resolve() / out.parent.name if make_parent else out.parent.resolve()) / out.name
        if _inside(out, dataset) or _inside(dataset, out):
            raise Refused("refused", "snapshot destination must be outside the dataset directory")
        names = sorted(dbs) if dbs else sorted(n for n in os.listdir(dataset) if _is_db_name(n))
        if not names:
            raise Refused("refused", "no SQLite databases found in the dataset (use --db NAME)")
        if len(names) > MAX_DATABASES:
            raise Refused("refused", f"more than {MAX_DATABASES} databases")
        for n in names:
            if not _is_db_name(n):
                raise Refused("invalid", f"{n!r} is not a plain database file name")
            if _lkind(dataset / n) != "file":
                raise Refused("refused", f"{n}: {_says(_lkind(dataset / n))}; expected a regular file")
        if make_parent:
            os.mkdir(out.parent, 0o755)
        return _locked(dataset, lambda: _snapshot_locked(dataset, out, names, lock_timeout))
    except Refused as exc:
        return _result(exc.status, messages=[str(exc)])
    except OSError as exc:
        return _result("failed", messages=[f"snapshot failed: {exc.strerror or exc}; no snapshot written"])


def _drop_copy_sidecars(tmp: Path, n: str) -> None:
    """The copy lives in a private .partial directory with no other connection. Some SQLite
    builds leave a -shm (and an empty -wal) next to it after the switch to DELETE mode; they
    hold no data, so remove them. A non-empty -wal would hold data, so that is a failure."""
    for suf in SIDECARS:
        side = tmp / (n + suf)
        kind = _lkind(side)
        if kind == "missing":
            continue
        if kind != "file" or (suf != "-shm" and side.stat().st_size):
            raise Refused("failed", f"{n}: the snapshot copy kept a {suf} file with data; no snapshot written")
        os.unlink(side)


def _snapshot_locked(dataset: Path, out: Path, names: List[str], lock_timeout: float) -> Dict[str, Any]:
    tmp = out.parent / f".{out.name}.{secrets.token_hex(6)}.partial"
    os.mkdir(tmp)
    try:
        dbinfo: Dict[str, Any] = {}
        for n in names:
            try:
                src = _open_live(dataset / n, timeout=lock_timeout)
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc) or "busy" in str(exc):
                    raise Refused("busy", f"{n} stayed locked for {lock_timeout:g}s; no snapshot written") from None
                raise Refused("refused", f"{n} could not be read as SQLite: {exc}") from None
            except sqlite3.DatabaseError as exc:
                raise Refused("refused", f"{n} could not be read as SQLite: {exc}") from None
            try:
                try:
                    src.execute("BEGIN")
                    src.execute("SELECT count(*) FROM sqlite_master").fetchone()
                except sqlite3.OperationalError as exc:
                    if "locked" in str(exc) or "busy" in str(exc):
                        raise Refused("busy", f"{n} stayed locked for {lock_timeout:g}s; no snapshot written") from None
                    raise
                src_digest = _digest(src)
                if src_digest["integrity"] != "ok":
                    raise Refused("refused", f"{n} fails integrity_check ({src_digest['integrity']}); not snapshotted")
                dst = sqlite3.connect(tmp / n)
                try:
                    src.backup(dst)
                    dst.execute("PRAGMA journal_mode=DELETE")
                finally:
                    dst.close()
                _drop_copy_sidecars(tmp, n)
                src.execute("ROLLBACK")
            except sqlite3.DatabaseError as exc:
                raise Refused("refused", f"{n} could not be read as SQLite: {exc}") from None
            finally:
                src.close()
            copy = _open_ro(tmp / n, immutable=True)
            try:
                copy_digest = _digest(copy)
            finally:
                copy.close()
            if copy_digest != src_digest:
                raise Refused("failed", f"{n}: snapshot copy does not match the source values")
            dbinfo[n] = dict(copy_digest, sha256=_sha_file(tmp / n), size=(tmp / n).stat().st_size)
        manifest = {"schema": SNAP_SCHEMA, "snapshot_id": secrets.token_hex(8), "created": _now(),
                    "dataset_name": dataset.name, "databases": dbinfo}
        _atomic_write(tmp / MANIFEST, (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        os.rename(tmp, out)
        _fsync_dir(out.parent)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return _result("ok", snapshot=str(out), snapshot_id=manifest["snapshot_id"],
                   databases={n: {"tables": {t: v["rows"] for t, v in d["tables"].items()}} for n, d in dbinfo.items()},
                   messages=[f"snapshot {manifest['snapshot_id']} written to {out}"])


# -- verify ---------------------------------------------------------------------------

def _load_snapshot(snap_arg: str) -> Tuple[Path, Dict[str, Any]]:
    snap = Path(snap_arg).expanduser()
    snap = snap if snap.is_absolute() else Path.cwd() / snap
    if _lkind(snap) != "directory":
        raise Refused("refused", f"snapshot {snap}: {_says(_lkind(snap))}; expected a real directory")
    snap = snap.resolve()
    if _lkind(snap / MANIFEST) != "file":
        raise Refused("refused", f"snapshot {MANIFEST}: {_says(_lkind(snap / MANIFEST))}; expected a regular file")
    try:
        manifest = json.loads((snap / MANIFEST).read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise Refused("refused", f"snapshot {MANIFEST} is not valid JSON") from None
    if not isinstance(manifest, dict) or manifest.get("schema") != SNAP_SCHEMA:
        raise Refused("refused", "snapshot manifest has an unknown format")
    dbs = manifest.get("databases")
    sid = manifest.get("snapshot_id")
    if not isinstance(sid, str) or not sid.isalnum() or not isinstance(dbs, dict) or not dbs:
        raise Refused("refused", "snapshot manifest lacks a snapshot id or databases")
    if len(dbs) > MAX_DATABASES or not all(_is_db_name(n) for n in dbs):
        raise Refused("refused", "snapshot manifest names a database with an unsafe or non-database name")
    for n, info in dbs.items():
        tables = info.get("tables") if isinstance(info, dict) else None
        if (not isinstance(info, dict) or not all(isinstance(info.get(k), str) for k in ("sha256", "integrity", "schema_digest"))
                or not isinstance(tables, dict)
                or not all(isinstance(t, str) and isinstance(v, dict) and isinstance(v.get("rows"), int)
                           and isinstance(v.get("digest"), str) for t, v in tables.items())):
            raise Refused("refused", f"snapshot manifest entry for {n} is malformed (needs sha256, integrity, "
                          "schema_digest and tables)")
    entries = set(os.listdir(snap))
    extra = sorted(entries - set(dbs) - {MANIFEST})
    if extra:
        raise Refused("refused", f"snapshot contains entries not in its manifest: {', '.join(extra[:5])}")
    return snap, manifest


def _verify_loaded(snap: Path, manifest: Dict[str, Any], expect: Optional[List[str]]) -> List[str]:
    problems: List[str] = []
    for n in expect or []:
        if n not in manifest["databases"]:
            problems.append(f"expected database {n} is not in the snapshot")
    for n, info in sorted(manifest["databases"].items()):
        kind = _lkind(snap / n)
        if kind != "file":
            problems.append(f"{n}: {kind}, expected a regular file")
            continue
        if _sha_file(snap / n) != info.get("sha256"):
            problems.append(f"{n}: sha256 mismatch (damaged)")
            continue
        try:
            con = _open_ro(snap / n, immutable=True)
            try:
                got = _digest(con)
            finally:
                con.close()
        except sqlite3.DatabaseError as exc:
            problems.append(f"{n}: unreadable as SQLite ({exc})")
            continue
        want = {k: info.get(k) for k in ("integrity", "schema_digest", "tables")}
        if got != want:
            bad = [t for t in set(got["tables"]) | set(want.get("tables") or {})
                   if got["tables"].get(t) != (want.get("tables") or {}).get(t)]
            what = f"tables {sorted(bad)}" if bad else "schema or header (user_version, application_id)"
            problems.append(f"{n}: content does not match manifest (integrity {got['integrity']}; {what})")
    return problems


def verify(snap_arg: str, expect: Optional[List[str]] = None) -> Dict[str, Any]:
    """Read-only: SQLite files are opened immutable, nothing is extracted or written."""
    try:
        snap, manifest = _load_snapshot(snap_arg)
    except Refused as exc:
        return _result("failed", messages=[str(exc)])
    problems = _verify_loaded(snap, manifest, expect)
    if problems:
        return _result("failed", snapshot_id=manifest["snapshot_id"], messages=problems)
    return _result("ok", snapshot_id=manifest["snapshot_id"], databases=sorted(manifest["databases"]),
                   messages=[f"snapshot {manifest['snapshot_id']} verified: {len(manifest['databases'])} databases, "
                             "sha256, integrity and per-table value digests match"])


# -- health ---------------------------------------------------------------------------

def health(dataset_arg: str, expect: List[str], snap_arg: Optional[str] = None,
           lock_timeout: float = DEFAULT_LOCK_TIMEOUT) -> Dict[str, Any]:
    try:
        dataset = _dataset_dir(dataset_arg)
        manifest = _load_snapshot(snap_arg)[1] if snap_arg else None
    except Refused as exc:
        return _result("invalid", messages=[str(exc)])
    names = list(dict.fromkeys(list(expect or []) + sorted((manifest or {}).get("databases", {}))))
    if not names:
        return _result("invalid", messages=["name the databases that must exist (--expect NAME) or give --snapshot"])
    problems, report = [], {}
    if _lkind(dataset / JOURNAL) != "missing":
        problems.append(f"{JOURNAL}: a restore is in progress or was interrupted; run `recover`")
    for n in names:
        if not _is_db_name(n):
            problems.append(f"{n!r} is not a plain database file name")
            continue
        kind = _lkind(dataset / n)
        if kind != "file":
            problems.append(f"{n}: expected database is {kind}")
            continue
        if (dataset / n).stat().st_size == 0:
            problems.append(f"{n}: empty file (0 bytes), not a database")
            continue
        try:
            con = _open_live(dataset / n, timeout=lock_timeout)
            try:
                got = _digest(con)
            finally:
                con.close()
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc) or "busy" in str(exc):
                problems.append(f"{n}: busy, another connection held it for {lock_timeout:g}s ({exc}); retry")
            else:
                problems.append(f"{n}: unreadable as SQLite ({exc})")
            continue
        except sqlite3.DatabaseError as exc:
            problems.append(f"{n}: unreadable as SQLite ({exc})")
            continue
        report[n] = {t: v["rows"] for t, v in got["tables"].items()}
        if got["integrity"] != "ok":
            problems.append(f"{n}: integrity_check {got['integrity']}")
        if not got["tables"] and not (manifest and n in manifest["databases"]):
            problems.append(f"{n}: has no user tables (an empty or emptied database); "
                            "give --snapshot to compare against a known good copy")
        if manifest and n in manifest["databases"]:
            want = manifest["databases"][n]
            diff = sorted(t for t in set(got["tables"]) | set(want["tables"])
                          if got["tables"].get(t) != want["tables"].get(t))
            if diff or got["schema_digest"] != want["schema_digest"]:
                problems.append(f"{n}: values differ from snapshot {manifest['snapshot_id']} in "
                                + (f"tables {diff}" if diff else "schema or header (user_version, application_id)"))
    if problems:
        return _result("unhealthy", databases=report, messages=problems)
    return _result("ok", databases=report, messages=[f"healthy: {', '.join(names)}"
                                                      + (f" match snapshot {manifest['snapshot_id']}" if manifest else "")])


# -- restore --------------------------------------------------------------------------

def _plan(dataset: Path, snap: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    """Read-only plan. Raises Refused for anything unsafe."""
    if _inside(snap, dataset) or _inside(dataset, snap):
        raise Refused("refused", "snapshot and dataset must not contain each other")
    if _lkind(dataset / JOURNAL) != "missing":
        raise Refused("refused", f"an interrupted restore is recorded in {JOURNAL}; run `recover` first")
    problems = _verify_loaded(snap, manifest, None)
    if problems:
        raise Refused("refused", "snapshot failed verification; target untouched: " + "; ".join(problems))
    sid = manifest["snapshot_id"]
    plan: Dict[str, Any] = {"snapshot_id": sid, "databases": {}, "untouched": [], "bytes": 0}
    for n, info in sorted(manifest["databases"].items()):
        entry: Dict[str, Any] = {"target": _lkind(dataset / n), "sidecars": []}
        if entry["target"] not in ("missing", "file"):
            raise Refused("refused", f"{n} in the dataset is a {entry['target']}; not replaced")
        for suf in SIDECARS:
            k = _lkind(dataset / (n + suf))
            if k not in ("missing", "file"):
                raise Refused("refused", f"{n}{suf} is a {k}; not replaced")
            if k == "file":
                entry["sidecars"].append(n + suf)
        if entry["target"] == "file":
            entry["changes"] = _compare(dataset / n, snap / n, info)
        else:
            entry["changes"] = {"summary": "database missing in the dataset; it will be created from the snapshot"}
        plan["databases"][n] = entry
        plan["bytes"] += int(info.get("size") or 0)
    plan["untouched"] = sorted(x for x in os.listdir(dataset)
                               if x not in plan["databases"] and not any(x == d + s for d in plan["databases"] for s in SIDECARS)
                               and x != LOCK)
    free = shutil.disk_usage(dataset).free
    if free < plan["bytes"] * 2 + (1 << 20):
        raise Refused("refused", f"not enough free space: need about {plan['bytes'] * 2} bytes, have {free}")
    return plan


def _compare(target: Path, snapfile: Path, info: Dict[str, Any]) -> Dict[str, Any]:
    """What the live database holds that the snapshot does not (read-only, immutable open)."""
    try:
        con = _open_ro(target, immutable=True)
    except sqlite3.DatabaseError as exc:
        return {"summary": f"current file unreadable ({exc}); kept as a recoverable copy"}
    try:
        try:
            cur = _digest(con)
        except sqlite3.DatabaseError as exc:
            return {"summary": f"current file unreadable ({exc}); kept as a recoverable copy"}
        snapcon = _open_ro(snapfile, immutable=True)
        try:
            only_target, differing = {}, []
            for t in sorted(set(cur["tables"]) | set(info["tables"])):
                if cur["tables"].get(t) == info["tables"].get(t):
                    continue
                differing.append(t)
                if t in cur["tables"]:
                    rows = _row_set(con, t) - (_row_set(snapcon, t) if t in info["tables"] else set())
                    if rows:
                        only_target[t] = len(rows)
        finally:
            snapcon.close()
    finally:
        con.close()
    wal = (target.parent / (target.name + "-wal")).exists()
    identical = (not differing and not wal and cur["integrity"] == "ok"
                 and cur["schema_digest"] == info.get("schema_digest"))
    summary = ("already matches the snapshot; left in place" if identical else "identical table values" if not differing else
               f"tables differing: {differing}; rows only in the live database: {only_target or 'none'}")
    if wal:
        summary += "; a -wal file exists, so uncheckpointed changes are not included in this comparison"
    return {"summary": summary, "differing_tables": differing, "rows_only_in_target": only_target, "identical": identical}


def restore(dataset_arg: str, snap_arg: str, confirm: Optional[str], dry_run: bool = False,
            lock_timeout: float = DEFAULT_LOCK_TIMEOUT, _crash_after: Optional[int] = None) -> Dict[str, Any]:
    plan: Optional[Dict[str, Any]] = None
    try:
        dataset = _dataset_dir(dataset_arg)
        snap, manifest = _load_snapshot(snap_arg)
        if dry_run:
            if _lock_held(dataset):
                raise Refused("busy", _lock_message(dataset))
            plan = _plan(dataset, snap, manifest)
            n_todo = sum(1 for e in plan["databases"].values()
                         if not (e["changes"].get("identical") and not e["sidecars"]))
            msgs = [f"dry run: would restore {n_todo} of {len(plan['databases'])} databases from snapshot "
                    f"{plan['snapshot_id']}; nothing written"]
            if confirm != manifest["snapshot_id"]:
                msgs.append(f"a real restore needs --confirm {manifest['snapshot_id']}")
            return _result("planned", plan=plan, messages=msgs)
        if _lock_held(dataset):
            raise Refused("busy", _lock_message(dataset))
        plan = _plan(dataset, snap, manifest)  # read-only refusal before any write
        if confirm != manifest["snapshot_id"]:
            raise Refused("refused", f"restore needs explicit intent: --confirm {manifest['snapshot_id']} "
                          f"(the plan below shows what the live files hold that the snapshot does not); nothing changed")
        return _locked(dataset, lambda: _restore_locked(dataset, snap, manifest, lock_timeout, _crash_after))
    except Refused as exc:
        res = _result(exc.status, messages=[str(exc)])
        if plan is not None:
            res["plan"] = plan
        return res
    except OSError as exc:
        return _result("failed", messages=[f"restore stopped: {exc.strerror or exc} ({Path(exc.filename).name if exc.filename else 'unknown path'}); "
                                           "run `recover` to finish or roll back"])


def _probe_quiet(path: Path, lock_timeout: float) -> Optional[str]:
    """Bounded check that no other connection holds the database. Returns a note."""
    try:
        con = sqlite3.connect(path, timeout=lock_timeout, isolation_level=None)
    except sqlite3.DatabaseError as exc:
        return f"{path.name}: not opened ({exc})"
    try:
        con.execute("BEGIN EXCLUSIVE")
        con.execute("ROLLBACK")
        return None
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc) or "busy" in str(exc):
            raise Refused("busy", f"{path.name} stayed locked for {lock_timeout:g}s; stop its writers and retry; "
                          "nothing changed") from None
        return f"{path.name}: lock probe skipped ({exc})"
    except sqlite3.DatabaseError as exc:
        return f"{path.name}: unreadable ({exc}); kept as a recoverable copy"
    finally:
        con.close()


def _steps_for(plan: Dict[str, Any], tag: str) -> List[Dict[str, str]]:
    steps: List[Dict[str, str]] = []
    for n, entry in sorted(plan["databases"].items()):
        if entry["changes"].get("identical") and not entry["sidecars"]:
            continue  # known good data stays where it is
        for side in entry["sidecars"]:
            steps.append({"from": side, "to": f"{side}.pre-restore-{tag}", "kind": "set_aside"})
        if entry["target"] == "file":
            steps.append({"from": n, "to": f"{n}.pre-restore-{tag}", "kind": "set_aside"})
        steps.append({"from": f".{n}.restore-{tag}.staged", "to": n, "kind": "install", "db": n})
    return steps


def _restore_locked(dataset: Path, snap: Path, manifest: Dict[str, Any], lock_timeout: float,
                    crash_after: Optional[int]) -> Dict[str, Any]:
    plan = _plan(dataset, snap, manifest)  # repeated under the lock
    sid = manifest["snapshot_id"]
    notes = [x for x in (_probe_quiet(dataset / n, lock_timeout) for n, e in plan["databases"].items()
                         if e["target"] == "file") if x]
    plan = _plan(dataset, snap, manifest)  # the probe may have created WAL sidecars; plan them too
    tag = f"{sid}-{secrets.token_hex(4)}"  # unique per run, so repeated restores never collide
    steps = _steps_for(plan, tag)
    if any(_lkind(dataset / x) != "missing" for st in steps for x in (st["to"],) if st["kind"] == "set_aside"):
        raise Refused("refused", "a rename destination already exists; nothing changed")
    todo = [s["db"] for s in steps if s["kind"] == "install"]
    if not todo:
        return _result("ok", snapshot_id=sid, restored=[], recoverable_copies=[], notes=notes,
                       messages=[f"every database already matches snapshot {sid}; nothing changed"])
    hashes = {n: manifest["databases"][n]["sha256"] for n in todo}
    journal = {"schema": JOURNAL_SCHEMA, "state": "staging", "snapshot_id": sid, "tag": tag, "started": _now(),
               "staged_sha256": {f".{n}.restore-{tag}.staged": h for n, h in hashes.items()}, "steps": steps}
    _atomic_write(dataset / JOURNAL, (json.dumps(journal, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    for n in todo:
        staged = dataset / f".{n}.restore-{tag}.staged"
        _copy_exclusive(snap / n, staged)
        if _sha_file(staged) != hashes[n]:
            raise Refused("failed", f"staged copy of {n} does not match the snapshot; run `recover` to clean up")
    _fsync_dir(dataset)
    journal["state"] = "swapping"
    _atomic_write(dataset / JOURNAL, (json.dumps(journal, indent=2, sort_keys=True) + "\n").encode("utf-8"))
    for i, step in enumerate(steps, 1):
        os.rename(dataset / step["from"], dataset / step["to"])
        _fsync_dir(dataset)
        if crash_after == i:
            os._exit(137)  # drill: simulate a killed process between renames
    res = _finish(dataset, journal, manifest)
    res["notes"] = notes
    return res


def _finish(dataset: Path, journal: Dict[str, Any], manifest: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Post-check installed databases against the journal/snapshot, then clear the journal."""
    sid = journal["snapshot_id"]
    installed = [s for s in journal["steps"] if s["kind"] == "install"]
    problems = []
    for s in installed:
        want = journal["staged_sha256"].get(s["from"])
        if _lkind(dataset / s["to"]) != "file" or _sha_file(dataset / s["to"]) != want:
            problems.append(f"{s['to']}: installed file does not match the snapshot copy")
    if problems:
        rb = _rollback(dataset, journal, len(journal["steps"]))
        rb["messages"] = problems + rb["messages"]
        return rb
    os.unlink(dataset / JOURNAL)
    _fsync_dir(dataset)
    kept = [s["to"] for s in journal["steps"] if s["kind"] == "set_aside"]
    return _result("ok", snapshot_id=sid, restored=[s["to"] for s in installed], recoverable_copies=kept,
                   messages=[f"restored {', '.join(s['to'] for s in installed)} from snapshot {sid}"]
                   + ([f"previous files kept: {', '.join(kept)}"] if kept else []))


# -- recover --------------------------------------------------------------------------

def _progress(dataset: Path, steps: List[Dict[str, str]]) -> Tuple[int, List[str]]:
    """How many leading renames completed, from the files actually present.

    Renames run strictly in order, so the true state is "first k done, rest not".
    Each k is checked by undoing the first k renames and applying the rest on a
    model of the directory; exactly one k must fit. A staged copy that vanished
    before its install is reported as lost. Raises Refused when nothing fits.
    """
    names = {n for s in steps for n in (s["from"], s["to"])}
    kinds = {n: _lkind(dataset / n) for n in names}
    odd = sorted(f"{n} is a {k}" for n, k in kinds.items() if k not in ("missing", "file"))
    if odd:
        raise Refused("needs_human", "unexpected entries; nothing changed: " + "; ".join(odd))
    present = {n for n, k in kinds.items() if k == "file"}
    fits = []
    for k in range(len(steps) + 1):
        state, ok = set(present), True
        for s in reversed(steps[:k]):
            if s["to"] in state and s["from"] not in state:
                state = (state - {s["to"]}) | {s["from"]}
            else:
                ok = False
                break
        if not ok:
            continue
        state, lost = set(present), []
        for s in steps[k:]:
            if s["from"] in state and s["to"] not in state:
                state = (state - {s["from"]}) | {s["to"]}
            elif s["kind"] == "install" and s["from"] not in state and s["to"] not in state:
                lost.append(s["from"])
            else:
                ok = False
                break
        if ok:
            fits.append((k, lost))
    if len(fits) != 1:
        raise Refused("needs_human", "cannot tell how far the swap got from the files present; nothing changed. "
                      f"Compare {JOURNAL} with the *.pre-restore-* copies by hand")
    return fits[0]


def _load_journal(dataset: Path) -> Optional[Dict[str, Any]]:
    kind = _lkind(dataset / JOURNAL)
    if kind == "missing":
        return None
    if kind != "file":
        raise Refused("needs_human", f"{JOURNAL} is a {kind}; nothing changed")
    try:
        j = json.loads((dataset / JOURNAL).read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise Refused("needs_human", f"{JOURNAL} is unreadable; nothing changed. Inspect it and the "
                      "*.pre-restore-* copies by hand") from None
    steps = j.get("steps") if isinstance(j, dict) else None
    if (not isinstance(j, dict) or j.get("schema") != JOURNAL_SCHEMA or j.get("state") not in ("staging", "swapping")
            or not isinstance(steps, list) or not isinstance(j.get("staged_sha256"), dict)):
        raise Refused("needs_human", f"{JOURNAL} has an unknown format; nothing changed")
    sid, tag = j.get("snapshot_id"), j.get("tag")
    if (not isinstance(sid, str) or not sid.isalnum() or not isinstance(tag, str)
            or not tag.startswith(sid + "-") or not tag[len(sid) + 1:].isalnum()):
        raise Refused("needs_human", f"{JOURNAL} lacks a valid snapshot id and run tag; nothing changed")
    for s in steps:
        ok = isinstance(s, dict) and all(isinstance(s.get(k), str) for k in ("from", "to"))
        if ok and s.get("kind") == "set_aside":
            base = s["from"]
            ok = (s["to"] == s["from"] + f".pre-restore-{tag}" and
                  (_is_db_name(base) or any(base.endswith(x) and _is_db_name(base[:-len(x)]) for x in SIDECARS)))
        elif ok and s.get("kind") == "install":
            ok = _is_db_name(s["to"]) and s["from"] == f".{s['to']}.restore-{tag}.staged" and s["from"] in j["staged_sha256"]
        else:
            ok = False
        if not ok:
            raise Refused("needs_human", f"{JOURNAL} lists a rename this tool never plans; nothing changed")
    return j


def recover(dataset_arg: str, dry_run: bool = False) -> Dict[str, Any]:
    try:
        dataset = _dataset_dir(dataset_arg)
        if dry_run:
            if _lock_held(dataset):
                raise Refused("busy", _lock_message(dataset))
            return _recover(dataset, dry_run=True)
        return _locked(dataset, lambda: _recover(dataset, dry_run=False))
    except Refused as exc:
        return _result(exc.status, messages=[str(exc)])
    except OSError as exc:
        return _result("failed", messages=[f"recover stopped: {exc.strerror or exc}; nothing beyond the listed "
                                           "renames happened; fix the cause and run recover again"])


JOURNAL_TEMP_RE = re.compile(r"^\." + re.escape(JOURNAL) + r"\.[0-9a-f]{16}\.tmp$")


def _journal_temps(dataset: Path) -> List[str]:
    """Temp files of a journal write that was killed before its rename (only our own pattern)."""
    return sorted(n for n in os.listdir(dataset) if JOURNAL_TEMP_RE.match(n) and _lkind(dataset / n) == "file")


def _recover(dataset: Path, dry_run: bool) -> Dict[str, Any]:
    temps = _journal_temps(dataset)
    if temps and not dry_run:
        for n in temps:
            os.unlink(dataset / n)
        _fsync_dir(dataset)
    res = _recover_journal(dataset, dry_run)
    if temps:
        res["removed_temp_files" if not dry_run else "would_remove_temp_files"] = temps
        res["messages"].append(("removed " if not dry_run else "would remove ") + f"{len(temps)} leftover journal temp file(s)")
    return res


def _recover_journal(dataset: Path, dry_run: bool) -> Dict[str, Any]:
    j = _load_journal(dataset)
    if j is None:
        return _result("nothing_to_do", messages=["no interrupted restore recorded; nothing changed"])
    staged = j["staged_sha256"]
    if j["state"] == "staging":
        own = [n for n in staged if _lkind(dataset / n) == "file"]
        if dry_run:
            return _result("planned", decision="discard_staging", messages=[
                f"interrupted before any swap: would remove {len(own)} staged copies; originals untouched"])
        for n in own:
            os.unlink(dataset / n)
        os.unlink(dataset / JOURNAL)
        _fsync_dir(dataset)
        return _result("ok", decision="discard_staging", messages=[
            "interrupted before any swap; staged copies removed, original files were never moved"])
    k, lost = _progress(dataset, j["steps"])
    pending_installs = [s for s in j["steps"][k:] if s["kind"] == "install" and s["from"] not in lost]
    bad = lost + [s["from"] for s in pending_installs if _sha_file(dataset / s["from"]) != staged.get(s["from"])]
    decision = "roll_back" if bad else "roll_forward"
    msg = (f"interrupted after {k} of {len(j['steps'])} renames; " +
           ("staged copies verify, completing the restore" if not bad else
            f"staged copies {bad} are missing or do not verify, putting the original files back"))
    if dry_run:
        return _result("planned", decision=decision, messages=[msg + " (dry run, nothing changed)"])
    if bad:
        res = _rollback(dataset, j, k)
    else:
        for s in j["steps"][k:]:
            os.rename(dataset / s["from"], dataset / s["to"])
            _fsync_dir(dataset)
        res = _finish(dataset, j, None)
    res["decision"] = decision
    res["messages"] = [msg] + res["messages"]
    return res


def _rollback(dataset: Path, j: Dict[str, Any], k: int) -> Dict[str, Any]:
    for s in reversed(j["steps"][:k]):
        os.rename(dataset / s["to"], dataset / s["from"])
        _fsync_dir(dataset)
    left = [s["from"] for s in j["steps"] if s["kind"] == "install" and _lkind(dataset / s["from"]) == "file"]
    os.unlink(dataset / JOURNAL)
    _fsync_dir(dataset)
    return _result("failed", decision="roll_back", kept=left, messages=[
        "original files are back in place; the restore did not happen"
        + (f"; staged copies kept for inspection: {', '.join(left)}" if left else "")])


# -- CLI ------------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("snapshot")
    p.add_argument("dataset")
    p.add_argument("--out", required=True)
    p.add_argument("--db", action="append")
    p.add_argument("--lock-timeout", type=float, default=DEFAULT_LOCK_TIMEOUT)
    p = sub.add_parser("verify")
    p.add_argument("snapshot")
    p.add_argument("--expect", action="append")
    p = sub.add_parser("health")
    p.add_argument("dataset")
    p.add_argument("--expect", action="append", default=[])
    p.add_argument("--snapshot")
    p.add_argument("--lock-timeout", type=float, default=DEFAULT_LOCK_TIMEOUT)
    p = sub.add_parser("restore")
    p.add_argument("dataset")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--confirm")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--lock-timeout", type=float, default=DEFAULT_LOCK_TIMEOUT)
    p.add_argument("--simulate-crash-after", type=int, help="drill only: exit 137 right after the Nth rename")
    p = sub.add_parser("recover")
    p.add_argument("dataset")
    p.add_argument("--dry-run", action="store_true")
    for sp in sub.choices.values():
        sp.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    lt = getattr(a, "lock_timeout", 1.0)
    if not math.isfinite(lt) or lt <= 0 or lt > 600:
        ap.error("--lock-timeout must be a number of seconds above 0 and at most 600")
    if a.cmd == "snapshot":
        res = snapshot(a.dataset, a.out, a.db, a.lock_timeout)
    elif a.cmd == "verify":
        res = verify(a.snapshot, a.expect)
    elif a.cmd == "health":
        res = health(a.dataset, a.expect, a.snapshot, a.lock_timeout)
    elif a.cmd == "restore":
        res = restore(a.dataset, a.snapshot, a.confirm, a.dry_run, a.lock_timeout, a.simulate_crash_after)
    else:
        res = recover(a.dataset, a.dry_run)
    if a.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        print(f"{a.cmd}: {res['status']}")
        for m in res.get("messages", []):
            print("  " + m)
        for n, e in sorted((res.get("plan") or {}).get("databases", {}).items()):
            print(f"  plan {n}: {e['changes']['summary']}")
        if res.get("plan", {}).get("untouched"):
            print(f"  untouched: {', '.join(res['plan']['untouched'])}")
    return res["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
