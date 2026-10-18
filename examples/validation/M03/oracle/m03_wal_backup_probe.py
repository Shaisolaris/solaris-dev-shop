"""Minimal probe, no candidate code: WAL source with a live writer, backup() to a new file, then
PRAGMA journal_mode=DELETE on the copy; report what the copy's directory holds after close."""
import os, sqlite3, sys, tempfile
d = tempfile.mkdtemp(prefix="m03probe-")
src_p, dst_dir = os.path.join(d, "src.db"), os.path.join(d, "out"); os.mkdir(dst_dir)
c = sqlite3.connect(src_p); c.execute("PRAGMA journal_mode=WAL"); c.execute("create table t(x)"); c.execute("insert into t values (1)"); c.commit(); c.close()
holder = sqlite3.connect(src_p); holder.execute("insert into t values (2)"); holder.commit()
for variant in ("default", "isolation_none"):
    for f in os.listdir(dst_dir): os.unlink(os.path.join(dst_dir, f))
    src = sqlite3.connect("file:%s?mode=ro" % src_p, uri=True, isolation_level=None)
    dst_p = os.path.join(dst_dir, "copy.db")
    dst = sqlite3.connect(dst_p) if variant == "default" else sqlite3.connect(dst_p, isolation_level=None)
    src.backup(dst)
    mode = dst.execute("PRAGMA journal_mode=DELETE").fetchone()[0]
    after_pragma = sorted(os.listdir(dst_dir))
    dst.close(); src.close()
    print(f"python {sys.version.split()[0]} sqlite {sqlite3.sqlite_version} [{variant}]: journal_mode->{mode}; "
          f"after pragma {after_pragma}; after close {sorted(os.listdir(dst_dir))}")
holder.close()
