"""M39: does os.killpg on an exited but not yet reaped session leader raise PermissionError on this OS?
This is the window in G19 boundary_oracle Server.stop(): poll() says running, the crash_after_commit server
exits, then killpg(pid, SIGTERM) runs before the child is reaped."""
import os, signal, subprocess, sys, time, platform
res = {}
for n in range(20):
    p = subprocess.Popen([sys.executable, "-c", "pass"], start_new_session=True)
    time.sleep(0.3)  # child has exited; not reaped yet (no wait/poll)
    try:
        os.killpg(p.pid, signal.SIGTERM); r = "no error"
    except PermissionError as e: r = "PermissionError: %s" % e
    except ProcessLookupError: r = "ProcessLookupError"
    res[r] = res.get(r, 0) + 1; p.wait()
print(platform.system(), platform.release(), sys.version.split()[0], res)
