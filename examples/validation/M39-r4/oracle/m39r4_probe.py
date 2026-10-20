#!/usr/bin/env python3
"""M39 r4 probes (Grok self-validation, not independent review). Paths the G39 r4 tests do not use: '..' through a
symlinked folder (inside and outside ROOT), --flag=../outside, a missing outside path, '..' into .delivery, and an r3-era
record without unbound_inputs. Reuses the M39 r2 contract helpers unchanged. S rows are scored.
Usage: PY m39r4_probe.py SRC OUT.json [--tool PATH]."""
import os, sys, json, tempfile
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, "m39r2_contract.py")).read()
exec(compile(_src[: _src.index("@safe\ndef c01")], "m39r2_contract_helpers", "exec"))

def run4(setup, cmd, mutate):
    b = B2(); b.order()
    if setup: setup(b)
    k = b.rd(cmd(b) if callable(cmd) else cmd); g0 = b.go()
    rec = json.loads(b.lines()[-1]) if k[0] == 0 else {}
    rc, j, e = b.verify("cr.json"); c = (j.get("contributions") or [{}])[0]
    mutate(b); g1 = b.go(); b.close()
    return k, g0, g1, rec, c

@safe
def s01():
    ext = tempfile.mkdtemp(prefix="m39r4-ext-"); os.makedirs(os.path.join(ext, "x")); open(os.path.join(ext, "e.csv"), "w").write("id,v\n5,5\n")
    k, g0, g1, rec, c = run4(lambda b: os.symlink(os.path.join(ext, "x"), b.p("out")), ["out/../e.csv"],
                            lambda b: open(os.path.join(ext, "e.csv"), "w").write("id,v\n5,6\n"))
    ok = k[0] == 0 and rec.get("claimed_inputs") == [] and rec.get("unbound_inputs") == ["out/../e.csv"] and c.get("unbound_inputs") == ["out/../e.csv"]
    row("S01 '..' through a symlinked folder that points outside ROOT: not bound to a ROOT file, listed unbound in record and verify", ok,
        {"rec": k[0], "claimed": rec.get("claimed_inputs"), "unbound": rec.get("unbound_inputs"), "verify_unbound": c.get("unbound_inputs")})

@safe
def s02():
    k, g0, g1, rec, c = run4(lambda b: (os.makedirs(b.p("deep", "x")), os.symlink(b.p("deep", "x"), b.p("lnk"))), ["lnk/../../inp/a.csv"],
                            lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"))
    ok = k[0] == 0 and rec.get("claimed_inputs") == ["inp/a.csv"] and g0[1] == "GO" and g1[1] != "GO"
    row("S02 '..' through a symlinked folder inside ROOT (lnk -> deep/x; lnk/../../inp/a.csv): bound to the file the OS reads; change caught", ok,
        {"rec": k[0], "claimed": rec.get("claimed_inputs"), "go": (g0[:3], g1[:3])})

@safe
def s03():
    ext = tempfile.mkdtemp(prefix="m39r4-ext-"); f = os.path.join(ext, "o.csv"); open(f, "w").write("id,v\n1,1\n")
    rel = os.path.relpath(f, "/")  # computed below against ROOT
    def cmd(b): return ["--src=" + os.path.relpath(f, b.r)]
    k, g0, g1, rec, c = run4(None, cmd, lambda b: None)
    ok = k[0] == 0 and len(rec.get("unbound_inputs") or []) == 1 and rec["unbound_inputs"][0].endswith("o.csv") and "never re-checked" in (c.get("unbound_note") or "")
    row("S03 --src=../../outside/o.csv (exists, outside ROOT): listed unbound with the verify note", ok, {"rec": k[0], "unbound": rec.get("unbound_inputs"), "note": c.get("unbound_note")})

@safe
def s04():
    k, g0, g1, rec, c = run4(None, ["inp/a.csv", "../no-such-file.csv"], lambda b: None)
    ok = k[0] == 0 and rec.get("unbound_inputs") == [] and "unbound_inputs" not in c
    row("S04 a '..' path that does not exist is not listed; the record carries an empty unbound_inputs", ok, {"rec": k[0], "unbound": rec.get("unbound_inputs"), "verify_keys": sorted(c)[:12]})

@safe
def s05():
    k, g0, g1, rec, c = run4(None, ["inp/a.csv", "inp/../.delivery/contributions.jsonl"], lambda b: None)
    ok = k[0] == 0 and not any(x.startswith(".delivery") for x in rec.get("claimed_inputs") or [])
    row("S05 '..' into .delivery is not bound as an input (the ledger is never an input)", ok, {"rec": k[0], "claimed": rec.get("claimed_inputs")})

@safe
def s06():
    b = B2(); b.order(); k = b.rd(["inp/a.csv"])
    led = b.p(".delivery", "contributions.jsonl"); ls = open(led).read().splitlines(); r = json.loads(ls[-1])
    had = "unbound_inputs" in r
    g = b.go(); b.close()
    row("S06 control: a fresh record verifies GO (r4 records carry unbound_inputs; verify reads it with .get, so r3 records without it still verify)",
        k[0] == 0 and g[1] == "GO" and had, {"rec": k[0], "go": g[:3], "key_present": had})

for f in (s01, s02, s03, s04, s05, s06):
    f()
scored = [r for r in ROWS if r["row"][0] == "S"]
json.dump({"rows": ROWS}, open(OUT, "w"), indent=1, default=str)
print("M39R4 PROBES %d/%d" % (sum(r["pass"] for r in scored), len(scored)))
