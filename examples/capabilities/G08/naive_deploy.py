#!/usr/bin/env python3
"""G08 naive control: the common shortcut deploy script, same CLI as local_deploy.py. Not for use.

Copies the artifact into releases/<revision>, runs migrate.sql, points `current` at it. It reads the plan but
checks no approval, environment, artifact digest, live health or rollback availability, takes no snapshot and
does not roll back on failure. `rollback` points `current` at the previous release folder (code only);
`preflight` and `recover` report success.
"""
import json
import os
import shutil
import sqlite3
import sys
from pathlib import Path


def main():
    cmd, plan_p = sys.argv[1], Path(sys.argv[2])
    plan = json.loads(plan_p.read_text())
    base = plan_p.resolve().parent
    env = base / plan["target"]
    if cmd in ("preflight", "recover", "status"):
        return 0
    rels = env / "releases"
    if cmd == "rollback":
        names = sorted(p.name for p in rels.iterdir() if not p.name.startswith("."))
        cur = Path(os.readlink(str(env / "current"))).name
        prev = [n for n in names if n < cur]
        if not prev:
            return 2
        os.unlink(str(env / "current"))
        os.symlink("releases/" + prev[-1], str(env / "current"))
        return 0
    rev = plan["artifact"]["revision"]
    rels.mkdir(exist_ok=True)
    dst = rels / rev
    if dst.exists():
        shutil.rmtree(str(dst))
    shutil.copytree(str(base / plan["artifact"]["path"]), str(dst))
    mig = dst / "migrate.sql"
    if mig.is_file():
        con = sqlite3.connect(str(env / "data" / "app.db"))
        try:
            con.executescript(mig.read_text())
        except sqlite3.Error:
            pass
        con.close()
    if "--fail-at" in sys.argv:
        os._exit(75)
    if os.path.lexists(str(env / "current")):
        os.unlink(str(env / "current"))
    os.symlink("releases/" + rev, str(env / "current"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
