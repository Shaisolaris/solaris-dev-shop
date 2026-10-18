"""M03 fault injector (only active when this folder is on PYTHONPATH and M03_KILL_ROOT is set).

M03_KILL_AT=N: SIGKILL just before the Nth rename-like event (os.rename, os.replace, os.unlink,
os.remove) on a path under M03_KILL_ROOT. M03_KILL_WRITE_AT=N: SIGKILL before the Nth open for
writing under the root. Files whose name ends in ".lock" are not counted. M03_EVENT_LOG=path
appends one line per counted event (kind, name) so a harness can see what it interrupted.
Implementation-agnostic: only the standard library is patched.
"""
import builtins
import os
import signal

_root = os.environ.get("M03_KILL_ROOT")
if _root:
    _root = os.path.realpath(_root)
    _at = int(os.environ.get("M03_KILL_AT", "0") or 0)
    _wat = int(os.environ.get("M03_KILL_WRITE_AT", "0") or 0)
    _log = os.environ.get("M03_EVENT_LOG")
    _n = [0, 0]

    def _under(path):
        try:
            p = os.path.realpath(os.fspath(path))
        except Exception:
            return None
        if (p == _root or p.startswith(_root + os.sep)) and not p.endswith(".lock"):
            return p
        return None

    def _event(kind, path, idx, limit):
        p = _under(path)
        if p is None:
            return
        _n[idx] += 1
        if _log:
            with _o_open(_log, "a") as fh:
                fh.write(f"{_n[idx]} {kind} {os.path.basename(p)}\n")
        if limit and _n[idx] >= limit:
            os.kill(os.getpid(), signal.SIGKILL)

    _o_open, _o_osopen = builtins.open, os.open
    _o_rename, _o_replace, _o_unlink, _o_remove = os.rename, os.replace, os.unlink, os.remove

    def _rename(a, b, *x, **k):
        _event("rename", b, 0, _at)
        return _o_rename(a, b, *x, **k)

    def _replace(a, b, *x, **k):
        _event("replace", b, 0, _at)
        return _o_replace(a, b, *x, **k)

    def _unlink(a, *x, **k):
        _event("unlink", a, 0, _at)
        return _o_unlink(a, *x, **k)

    def _remove(a, *x, **k):
        _event("remove", a, 0, _at)
        return _o_remove(a, *x, **k)

    def _open(file, mode="r", *a, **k):
        if isinstance(file, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+"):
            _event("open-w", file, 1, _wat)
        return _o_open(file, mode, *a, **k)

    def _osopen(path, flags, *a, **k):
        if flags & (os.O_WRONLY | os.O_RDWR):
            _event("osopen-w", path, 1, _wat)
        return _o_osopen(path, flags, *a, **k)

    os.rename, os.replace, os.unlink, os.remove = _rename, _replace, _unlink, _remove
    builtins.open, os.open = _open, _osopen
