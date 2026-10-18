"""Minimal probe, no candidate code: replays sqlite_recovery.py snapshot's read path step by step on a
quiescent WAL database (journal_mode=WAL set, all connections closed, so no -wal/-shm on disk)."""
import os, sqlite3, sys, tempfile
from pathlib import Path
d = Path(tempfile.mkdtemp(prefix="m03st-", dir="/tmp")); p = d / "app.db"
c = sqlite3.connect(p); c.execute("create table t(x)"); c.execute("insert into t values (1)"); c.commit(); c.close()
c = sqlite3.connect(p); c.execute("PRAGMA journal_mode=WAL"); c.close()
steps = []
def step(name, fn):
    try:
        r = fn(); steps.append(f"{name}=ok"); return r
    except sqlite3.Error as e:
        steps.append(f"{name}=ERR({e})"); return None
before = sorted(os.listdir(d))
src = step("connect_ro", lambda: sqlite3.connect(p.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None))
if src:
    step("begin", lambda: src.execute("BEGIN"))
    step("select_master", lambda: src.execute("SELECT count(*) FROM sqlite_master").fetchone())
    step("integrity_check", lambda: src.execute("PRAGMA integrity_check").fetchall())
    src.close()
print(f"python {sys.version.split()[0]} sqlite {sqlite3.sqlite_version}: files before {before}; " + ", ".join(steps) + f"; files after {sorted(os.listdir(d))}")
