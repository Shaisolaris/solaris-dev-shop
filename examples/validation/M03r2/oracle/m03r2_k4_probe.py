"""r2 probe: replay m03_oracle k4 kill points one by one with event logs and directory listings.
Usage: PY m03r2_k4_probe.py PY TOOL N1,N2,... [--health] [--clean-new-sidecars]
--clean-new-sidecars: after a needs_human recover, list sidecar sizes, remove the -wal/-shm that health created, recover again.
--health runs `health --expect app.db --expect audit.db` between the kill and recover, as k4 does."""
import sys, tempfile, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import m03_oracle as M
M.CMD = [sys.argv[1], sys.argv[2]]
tmp = Path(tempfile.mkdtemp(prefix="m03r2-k4probe-")).resolve()
def ls(ds):
    return sorted(p.name + ("/" if p.is_dir() else "") for p in ds.iterdir())
try:
    for n in [int(x) for x in sys.argv[3].split(",")]:
        base, ds = M.fixture(tmp, f"p{n}")
        snap = base / "snap"; sid = M.snap_id(ds, snap); M.mutate(ds, "1")
        v_live = M.vals(ds); v_snap = {k: M.values(snap / k) for k in ("app.db", "audit.db")}
        log = base / "events.log"
        rc, out, _ = M.run("restore", ds, "--snapshot", snap, "--confirm", sid,
                           extra={"M03_KILL_ROOT": str(ds), "M03_KILL_AT": str(n), "M03_EVENT_LOG": str(log), "PYTHONPATH": str(M.INJECT)})
        print(f"=== kill@{n} restore rc={rc}")
        print("events:", log.read_text().replace("\n", "; ") if log.exists() else "-")
        print("after kill:", ls(ds))
        cur = M.vals(ds)
        print("after kill values: app", "live" if cur["app.db"] == v_live["app.db"] else "snap" if cur["app.db"] == v_snap["app.db"] else repr(cur["app.db"])[:60],
              "| audit", "live" if cur["audit.db"] == v_live["audit.db"] else "snap" if cur["audit.db"] == v_snap["audit.db"] else repr(cur["audit.db"])[:60])
        if "--health" in sys.argv:
            rc, out, _ = M.run("health", ds, "--expect", "app.db", "--expect", "audit.db")
            print(f"health rc={rc}:", out.strip().replace("\n", " | ")[:400])
            print("after health:", ls(ds))
        rc, out, _ = M.run("recover", ds)
        print(f"recover rc={rc}:", out.strip().replace("\n", " | ")[:700])
        print("after recover:", ls(ds))
        cur = M.vals(ds)
        print("after recover values: app", "live" if cur["app.db"] == v_live["app.db"] else "snap" if cur["app.db"] == v_snap["app.db"] else repr(cur["app.db"])[:60],
              "| audit", "live" if cur["audit.db"] == v_live["audit.db"] else "snap" if cur["audit.db"] == v_snap["audit.db"] else repr(cur["audit.db"])[:60])
        print("state:", M._old_and_new_kept(ds, v_live, v_snap))
        if "--clean-new-sidecars" in sys.argv and "needs_human" in out:
            for nm in ("audit.db-wal", "audit.db-shm", "app.db-wal", "app.db-shm"):
                if (ds / nm).exists():
                    print(f"  {nm}: {(ds / nm).stat().st_size} bytes; removing"); (ds / nm).unlink()
            rc, out, _ = M.run("recover", ds)
            print(f"recover again rc={rc}:", out.strip().replace("\n", " | ")[:400])
            print("state after cleanup:", M._old_and_new_kept(ds, v_live, v_snap))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
