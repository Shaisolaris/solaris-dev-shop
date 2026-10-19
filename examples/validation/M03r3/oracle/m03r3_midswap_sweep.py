"""M03 r3 (Grok self-validation): R-A class sweep. For each kill point of a restore of a
WAL dataset, run every other command against the half-swapped dataset and require that
none of them creates, removes or changes any file (names, sizes, mtimes), and that
`recover` afterwards ends whole (all live or all snapshot) with both copies kept.
Usage: PY m03r3_midswap_sweep.py PY TOOL N1,N2,..."""
import os, sys, tempfile, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import m03_oracle as M
M.CMD = [sys.argv[1], sys.argv[2]]
tmp = Path(tempfile.mkdtemp(prefix="m03r3-sweep-")).resolve()

def state(ds):
    out = {}
    for p in sorted(ds.rglob("*")):
        st = p.lstat()
        out[str(p.relative_to(ds))] = (st.st_size, st.st_mtime_ns, st.st_ino)
    return out

def diff(a, b):
    return {"added": sorted(set(b) - set(a)), "removed": sorted(set(a) - set(b)),
            "changed": sorted(k for k in set(a) & set(b) if a[k] != b[k])}

fail = 0
for n in [int(x) for x in sys.argv[3].split(",")]:
    base, ds = M.fixture(tmp, f"s{n}")
    snap = base / "snap"; sid = M.snap_id(ds, snap); M.mutate(ds, "1")
    v_live = M.vals(ds); v_snap = {k: M.values(snap / k) for k in ("app.db", "audit.db")}
    rc, _, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid,
                     extra={"M03_KILL_ROOT": str(ds), "M03_KILL_AT": str(n), "PYTHONPATH": str(M.INJECT)})
    journal = (ds / ".solaris-recovery.json").exists()
    print(f"=== kill@{n} restore rc={rc} journal={'present' if journal else 'absent'}")
    if not journal:
        print("  (no journal at this point; sweep not applicable)")
        continue
    cmds = [("health", ["health", ds, "--expect", "app.db", "--expect", "audit.db"]),
            ("health --snapshot", ["health", ds, "--snapshot", snap]),
            ("snapshot to new dir", ["snapshot", ds, "--out", base / "snapnew"]),
            ("snapshot into missing parent", ["snapshot", ds, "--out", base / "missing" / "x"]),
            ("restore --dry-run", ["restore", ds, "--snapshot", snap, "--dry-run"]),
            ("restore --confirm", ["restore", ds, "--snapshot", snap, "--confirm", sid]),
            ("verify snapshot", ["verify", snap]),
            ("recover --dry-run", ["recover", ds, "--dry-run"])]
    for name, args in cmds:
        before = state(ds); outside_before = sorted(p.name for p in base.iterdir())
        rc, out, _ = M.run(*args)
        d = diff(before, state(ds)); outside = sorted(p.name for p in base.iterdir())
        wrote = any(d.values()) or outside != outside_before
        first = out.strip().splitlines()[0] if out.strip() else ""
        print(f"  {name:30} rc={rc} {'WROTE ' + json.dumps(d) + (' outside:' + str(sorted(set(outside) ^ set(outside_before))) if outside != outside_before else '') if wrote else 'no file change'} | {first[:110]}")
        if wrote and name != "restore --confirm":
            fail += 1
        if wrote and name == "restore --confirm":
            fail += 1
    rc, out, _ = M.run("recover", ds)
    st = M._old_and_new_kept(ds, v_live, v_snap)
    print(f"  recover rc={rc} state={st} | {out.strip().splitlines()[0][:120] if out.strip() else ''}")
    if rc != 0 or st[0] not in ("forward", "back") or not st[1]:
        fail += 1
print("SWEEP", "OK" if not fail else f"FAIL ({fail})")
sys.exit(1 if fail else 0)
