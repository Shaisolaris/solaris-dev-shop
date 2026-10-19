#!/usr/bin/env python3
"""M23 r2: distinguishing inputs for the r2 survivors (Grok self-validation). Usage: PY survivor_distinguish_r2.py"""
import json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import make_mutants_r2 as MM
REL = "employees/specialized/wordpress-master/wp_trace_diag.py"; base = "/tmp/m23r2-eval/" + REL; src = open(base).read()
B = {"schema": "solaris.wp-trace/1", "site": "s", "environment": "production", "source": "Grok M23 r2 distinguish, synthetic",
     "env": {"php": "8.3.0", "wp": "6.6.2", "host": "h"}, "measurement": {"tool": "t", "warm_cache": False, "runs_per_url": 5, "concurrency": 1},
     "wp_config": {}, "dropins": [], "active_plugins": [], "autoload_bytes": 1, "autoload_top": [], "system_cron": True, "php_errors": [], "bisect": []}
SQ = "SELECT * FROM wp_x WHERE a = 1"
cases = {"r2_slowest_ge": (["--json"], [{"sql": SQ, "ms": 200, "source_file": "A.log", "source_line": 1}, {"sql": SQ, "ms": 200, "source_file": "B.log", "source_line": 2}]),
         "r2_text_more_6": ([], [{"sql": SQ, "ms": 200 + i, "source_file": "s.log", "source_line": i + 1} for i in range(6)])}
d = tempfile.mkdtemp(prefix="m23r2-dist-", dir="/tmp")
for name, (flags, qs) in cases.items():
    old, new = [(m[1], m[2]) for m in MM.M if m[0] == name][0]
    mp = os.path.join(d, name + ".py"); open(mp, "w").write(MM.apply(src, old, new))
    b = dict(B, requests=[{"id": "r", "url": "/", "total_ms": 900, "queries": qs, "hooks": []}]); bp = os.path.join(d, name + ".json"); json.dump(b, open(bp, "w"))
    outs = {}
    for tag, tool in (("base", base), ("mutant", mp)):
        cp = subprocess.run([sys.executable, tool, "diagnose", bp] + flags, capture_output=True, text=True)
        outs[tag] = ([f["evidence"] for f in json.loads(cp.stdout)["findings"]] if flags else [l.strip() for l in cp.stdout.splitlines() if "sources" in l])
    print(name, "DIFFERENT" if outs["base"] != outs["mutant"] else "SAME", json.dumps(outs))
shutil.rmtree(d)
