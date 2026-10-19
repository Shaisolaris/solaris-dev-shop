#!/usr/bin/env python3
"""M23 r1: distinguishing inputs for teeth survivors (Grok self-validation). Runs the candidate and each mutant
(written to /tmp/m23-dist-*) on an input chosen to separate them, and prints exit codes and finding codes."""
import json, os, shutil, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import make_mutants_g23 as MM
PY = sys.argv[1]
SRC = "/tmp/m23r2-eval/employees/specialized/wordpress-master/wp_trace_diag.py"
src = open(SRC).read(); M = {n: (o, w) for n, o, w in MM.M}
W = tempfile.mkdtemp(prefix="m23-dist-", dir="/tmp")
def tool(name):
    if name == "candidate":
        return SRC
    p = os.path.join(W, name + ".py"); open(p, "w").write(MM.apply(src, *M[name])); return p
B = {"schema": "solaris.wp-trace/1", "site": "d", "environment": "production", "source": "distinguishing input"}
def run(t, args):
    cp = subprocess.run([PY, t] + args, capture_output=True, text=True, timeout=60)
    try:
        c = [f["code"] for f in json.loads(cp.stdout)["findings"]]
    except Exception:
        c = cp.stderr.strip()[-90:]
    return cp.returncode, c
cases = []
# nan_allowed: NaN in every numeric field kind
for field in ['"total_ms": NaN', '"ms": NaN', '"peak_memory_mb": NaN', '"autoload_bytes": NaN']:
    b = dict(B, autoload_bytes=1, requests=[{"id": "r", "url": "/", "total_ms": 1.0, "peak_memory_mb": 1.0, "queries": [{"sql": "SELECT 1", "ms": 1.0}]}])
    txt = json.dumps(b).replace('"' + field.split('"')[1] + '": 1.0', field, 1).replace('"autoload_bytes": 1', field, 1) if "autoload" in field else json.dumps(b).replace('"' + field.split('"')[1] + '": 1.0', field, 1)
    p = os.path.join(W, "nan%d.json" % len(cases)); open(p, "w").write(txt)
    cases.append(("nan_allowed", field, [p, "--json"]))
# out_symlink_allowed: --out is a symlink to an unrelated file
other = os.path.join(W, "other.txt"); open(other, "w").write("KEEP")
ok = os.path.join(W, "ok.json"); json.dump(B, open(ok, "w"))
link = os.path.join(W, "out-link.json")
cases.append(("out_symlink_allowed", "--out is a symlink", [ok, "--out", link]))
# component_no_unknown: a query whose component is the documented value "unknown"
u = os.path.join(W, "unk.json"); json.dump(dict(B, requests=[{"id": "r", "url": "/", "total_ms": 90.0, "queries": [{"sql": "SELECT * FROM wp_x", "ms": 80.0, "caller": "unknown", "component": "unknown"}]}]), open(u, "w"))
cases.append(("component_no_unknown", 'component "unknown"', [u, "--json"]))
# pair_skip_unknown_side: redeclare where the first declarer is outside wp-content
line = "[18-Oct-2026 10:00:00 UTC] PHP Fatal error:  Cannot redeclare f_x() (previously declared in /usr/share/php/lib.php:4) in /srv/www/wp-content/plugins/beta/b.php on line 9"
pu = os.path.join(W, "pu.json"); json.dump(dict(B, php_errors=[line]), open(pu, "w"))
cases.append(("pair_skip_unknown_side", "first declarer outside wp-content", [pu, "--json"]))
out = []
for name, what, args in cases:
    for t in ("candidate", name):
        if os.path.lexists(link):
            os.unlink(link)
        if name == "out_symlink_allowed":
            os.symlink(other, link)
        rc, c = run(tool(t), ["diagnose"] + args)
        extra = {"link_still_symlink": os.path.islink(link), "other_intact": open(other).read() == "KEEP"} if name == "out_symlink_allowed" else {}
        row = {"mutant": name, "input": what, "subject": t, "rc": rc, "codes": c, **extra}
        out.append(row); print(json.dumps(row))
shutil.rmtree(W)
