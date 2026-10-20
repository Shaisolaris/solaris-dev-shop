#!/usr/bin/env python3
"""M19 h1 stop() probe (Grok self-validation, not independent review). Checks that the widened except clauses in
boundary_oracle.Server.stop() do not hide a server that is really still running: a child that ignores SIGTERM must
still be killed (SIGKILL fallback), and a normal child must stop. Usage: PY m19h1_stop_probe.py TREE OUT.json"""
import importlib.util, json, os, subprocess, sys, time
T = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; rows = []
spec = importlib.util.spec_from_file_location("bo", os.path.join(T, "examples/capabilities/G19/boundary_oracle.py"))
bo = importlib.util.module_from_spec(spec); spec.loader.exec_module(bo)
def mk(code):
    s = object.__new__(bo.Server)
    s.proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, start_new_session=True)
    time.sleep(0.5); return s
for name, code in (("child that ignores SIGTERM is still killed", "import signal,time\nsignal.signal(signal.SIGTERM, signal.SIG_IGN)\ntime.sleep(60)"),
                   ("normal child stops on SIGTERM", "import time\ntime.sleep(60)")):
    s = mk(code); t0 = time.time(); err = None
    try: s.stop()
    except Exception as e: err = repr(e)
    rc = s.proc.poll(); ok = rc is not None and err is None
    rows.append({"row": name, "pass": ok, "detail": {"returncode": rc, "error": err, "seconds": round(time.time() - t0, 1)}})
    print(("PASS " if ok else "FAIL ") + name, rows[-1]["detail"])
json.dump({"rows": rows}, open(OUT, "w"), indent=1)
print("M19H1 STOP PROBE %d/%d" % (sum(r["pass"] for r in rows), len(rows)))
