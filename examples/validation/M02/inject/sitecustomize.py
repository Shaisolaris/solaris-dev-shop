"""M02 fault injector (loaded only when this folder is on PYTHONPATH).

When M02_KILL_ROOT and M02_KILL_AT=N are set, the process SIGKILLs itself just
before its Nth write-like filesystem event (open for writing, os.open with a
write flag, os.replace, os.rename) under M02_KILL_ROOT. Lock files are not
counted. With M02_SLOW_MS=N (and M02_KILL_ROOT) every counted event first sleeps N ms,
which models a slow disk and widens race windows. Implementation-agnostic: it patches
the standard library only.
"""
import builtins
import os
import signal

_root = os.environ.get("M02_KILL_ROOT")
_at = int(os.environ.get("M02_KILL_AT", "0") or 0)
_slow = int(os.environ.get("M02_SLOW_MS", "0") or 0) / 1000.0
if _root and (_at > 0 or _slow > 0):
    import time
    _root = os.path.realpath(_root)
    _count = [0]

    def _hit(path):
        try:
            p = os.path.realpath(os.fspath(path))
        except Exception:
            return
        if (p == _root or p.startswith(_root + os.sep)) and not p.endswith(".lock"):
            _count[0] += 1
            if _slow:
                time.sleep(_slow)
            if _at and _count[0] >= _at:
                os.kill(os.getpid(), signal.SIGKILL)

    _o_open, _o_osopen, _o_replace, _o_rename = builtins.open, os.open, os.replace, os.rename

    def _open(file, mode="r", *a, **k):
        if isinstance(file, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+"):
            _hit(file)
        return _o_open(file, mode, *a, **k)

    def _osopen(path, flags, *a, **k):
        if flags & (os.O_WRONLY | os.O_RDWR):
            _hit(path)
        return _o_osopen(path, flags, *a, **k)

    def _replace(src, dst, *a, **k):
        _hit(dst)
        return _o_replace(src, dst, *a, **k)

    def _rename(src, dst, *a, **k):
        _hit(dst)
        return _o_rename(src, dst, *a, **k)

    builtins.open, os.open, os.replace, os.rename = _open, _osopen, _replace, _rename
