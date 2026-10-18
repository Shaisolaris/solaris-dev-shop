"""Same quiescent-WAL read-only open through a chosen libsqlite3 via ctypes (varies the library, not Python)."""
import ctypes, os, sys, tempfile
lib = ctypes.CDLL(sys.argv[1]); lib.sqlite3_libversion.restype = ctypes.c_char_p
lib.sqlite3_open_v2.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_int, ctypes.c_char_p]
lib.sqlite3_exec.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
lib.sqlite3_close.argtypes = [ctypes.c_void_p]; lib.sqlite3_errmsg.argtypes = [ctypes.c_void_p]; lib.sqlite3_errmsg.restype = ctypes.c_char_p
d = tempfile.mkdtemp(prefix="m03lr-", dir="/tmp"); p = os.path.join(d, "app.db").encode()
db = ctypes.c_void_p(); lib.sqlite3_open_v2(p, ctypes.byref(db), 0x2 | 0x4, None)
for s in (b"create table t(x)", b"insert into t values (1)", b"PRAGMA journal_mode=WAL"): lib.sqlite3_exec(db, s, None, None, None)
lib.sqlite3_close(db)
before = sorted(os.listdir(d)); ro = ctypes.c_void_p()
rc_open = lib.sqlite3_open_v2(b"file:" + p + b"?mode=ro", ctypes.byref(ro), 0x1 | 0x40, None)
rc = lib.sqlite3_exec(ro, b"SELECT count(*) FROM sqlite_master", None, None, None)
print(f"python {sys.version.split()[0]} lib {sys.argv[1]} sqlite {lib.sqlite3_libversion().decode()}: before {before}; open rc={rc_open}, select rc={rc} ({lib.sqlite3_errmsg(ro).decode()})")
lib.sqlite3_close(ro)
