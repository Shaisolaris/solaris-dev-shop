# M02 r2 fault injector (Grok self-validation). Standard library only; patches os.replace.
# M02R2_KILL_AT=N : SIGKILL this process just before the Nth os.replace (temp file already written).
import os, signal
_n = int(os.environ.get("M02R2_KILL_AT", "0") or 0)
if _n > 0:
    _orig = os.replace
    _count = [0]
    def _replace(src, dst, *a, **k):
        _count[0] += 1
        if _count[0] == _n:
            os.kill(os.getpid(), signal.SIGKILL)
        return _orig(src, dst, *a, **k)
    os.replace = _replace
