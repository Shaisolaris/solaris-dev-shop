#!/usr/bin/env python3
"""Run a command with a wall-clock limit (macOS has no `timeout`). Usage: tmo.py SECONDS cmd ...
Exit 124 and SIGKILL the child when the limit is hit; prints elapsed seconds to stderr."""
import subprocess
import sys
import time

lim = float(sys.argv[1])
t0 = time.time()
p = subprocess.Popen(sys.argv[2:])
try:
    rc = p.wait(timeout=lim)
except subprocess.TimeoutExpired:
    p.kill()
    p.wait()
    rc = 124
print(f"[elapsed {time.time() - t0:.1f}s]", file=sys.stderr)
sys.exit(rc)
