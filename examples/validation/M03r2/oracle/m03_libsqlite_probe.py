"""Same WAL->DELETE conversion through the C API of a chosen libsqlite3 via ctypes, so the SQLite
library can be varied independently of the Python version. Usage: python m03_libsqlite_probe.py LIB"""
import ctypes, os, sys, tempfile
lib = ctypes.CDLL(sys.argv[1])
lib.sqlite3_libversion.restype = ctypes.c_char_p
lib.sqlite3_open.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
lib.sqlite3_exec.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.sqlite3_close.argtypes = [ctypes.c_void_p]
d = tempfile.mkdtemp(prefix="m03lib-"); p = os.path.join(d, "x.db")
db = ctypes.c_void_p(); assert lib.sqlite3_open(p.encode(), ctypes.byref(db)) == 0
for s in (b"PRAGMA journal_mode=WAL", b"create table t(x)", b"insert into t values (1)", b"PRAGMA journal_mode=DELETE"):
    assert lib.sqlite3_exec(db, s, None, None, None) == 0, s
lib.sqlite3_close(db)
print(f"python {sys.version.split()[0]} lib {sys.argv[1]} sqlite {lib.sqlite3_libversion().decode()}: after WAL->DELETE and close: {sorted(os.listdir(d))}")
