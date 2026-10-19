"""M03 r3 (Grok self-validation): snapshot's missing-parent folder (R-B fix) edge cases.
Usage: PY m03r3_parent_probes.py PY TOOL. Prints OK / FINDING / NOTE per case."""
import os, sqlite3, subprocess, sys, tempfile
from pathlib import Path
PY, TOOL = sys.argv[1], sys.argv[2]
ROOT = Path(tempfile.mkdtemp(prefix="m03r3p-")).resolve()
def run(*a):
    p = subprocess.run([PY, TOOL, *map(str, a)], capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    return p.returncode, (p.stdout.strip().splitlines() or [""])[0]
def ds(name, wal=False, broken=None):
    d = ROOT / name / "data"; d.mkdir(parents=True)
    for n in ("app.db", "audit.db"):
        c = sqlite3.connect(d / n)
        if wal: c.execute("PRAGMA journal_mode=WAL")
        c.execute("create table t(id integer primary key, v text)"); c.execute("insert into t(v) values ('a')"); c.commit(); c.close()
    if broken == "zero": (d / "app.db").write_bytes(b"")
    if broken == "garbage": (d / "app.db").write_bytes(b"not a database" * 100)
    if broken == "tableless":
        os.unlink(d / "app.db"); sqlite3.connect(d / "app.db").close()
    return d
res = []
def case(name, ok, detail):
    res.append(ok); print(("OK " if ok else "FINDING ") + name + ": " + detail)
for broken in ("zero", "garbage", "tableless"):
    d = ds("b-" + broken, broken=broken); parent = d.parent / "snaps"
    rc, first = run("snapshot", d, "--out", parent / "s1")
    case(f"p1_{broken}_db_missing_parent", rc != 0 and not parent.exists(),
         f"exit {rc} ({first[:90]}); parent exists after: {parent.exists()}")
d = ds("pre"); parent = d.parent / "snaps"; parent.mkdir(); (parent / "keep.txt").write_text("x")
os.unlink(d / "app.db"); sqlite3.connect(d / "app.db").close()
rc, first = run("snapshot", d, "--out", parent / "s1")
case("p2_failed_snapshot_keeps_preexisting_parent", parent.is_dir() and (parent / "keep.txt").exists() and sorted(os.listdir(parent)) == ["keep.txt"],
     f"exit {rc}; parent listing after: {sorted(os.listdir(parent)) if parent.exists() else 'GONE'}")
d = ds("emptypre"); parent = d.parent / "snaps"; parent.mkdir()
os.unlink(d / "app.db"); sqlite3.connect(d / "app.db").close()
rc, first = run("snapshot", d, "--out", parent / "s1")
case("p3_failed_snapshot_keeps_preexisting_empty_parent", parent.is_dir(), f"exit {rc}; parent exists after: {parent.exists()}")
for wal in (False, True):
    d = ds(f"good-{wal}", wal=wal); parent = d.parent / "snaps"
    rc, first = run("snapshot", d, "--out", parent / "s1")
    leftovers = sorted(p.name for p in parent.iterdir() if p.name != "s1") if parent.exists() else None
    case(f"p4_ok_snapshot_missing_parent_wal={wal}", rc == 0 and (parent / "s1").is_dir() and leftovers == [],
         f"exit {rc} ({first[:60]}); s1 present {(parent / 's1').is_dir()}; other entries {leftovers}")
d = ds("deep"); rc, first = run("snapshot", d, "--out", d.parent / "a" / "b" / "s1")
case("p5_two_missing_levels_refused_nothing_created", rc == 2 and not (d.parent / "a").exists(), f"exit {rc}; a/ exists {(d.parent / 'a').exists()}")
print("PROBES", "OK" if all(res) else f"FINDINGS {res.count(False)}")
