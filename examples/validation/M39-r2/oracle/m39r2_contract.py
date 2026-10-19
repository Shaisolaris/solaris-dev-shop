#!/usr/bin/env python3
"""M39 r2 contract oracle (Grok self-validation, not independent review). Written from root's ROOT-FINDINGS item 8
(bind explicit and indirect inputs, complete output-folder membership, exit 2 never counts as GO, honest exit and gap
verdicts) and the G39 r2 doc, beyond the M39 oracle. It reuses the M39 oracle's Box helpers unchanged (the source above
its first row is executed here). C rows are scored; Q rows are observations (always pass, not scored).
Usage: PY m39r2_contract.py SRC OUT.json [--tool PATH]."""
import os, sys
_here = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(_here, "m39_oracle.py")).read()
exec(compile(_src[: _src.index("@safe\ndef d01")], "m39_oracle_helpers", "exec"))

READ = ("import sys,os,hashlib\n"
        "a=[x for x in sys.argv[1:]]\nsrc=None;out=a[-1]\n"
        "for i,x in enumerate(a[:-1]):\n"
        "    if x.startswith('--src='): src=x[6:]\n"
        "    elif x=='--src': src=a[i+1]\n"
        "    elif not x.startswith('-') and src is None and (i==0 or a[i-1]!='--src'): src=x\n"
        "if src is None: src='inp/hidden.csv'\n"
        "def files(p):\n"
        "    if os.path.isdir(p):\n"
        "        return [os.path.join(d,f) for d,_,fs in sorted(os.walk(p)) for f in sorted(fs)]\n"
        "    return [p]\n"
        "h=hashlib.sha256()\n"
        "for f in files(src): h.update(open(f,'rb').read())\n"
        "try:\n    import helper; h.update(helper.SALT.encode())\nexcept ImportError: pass\n"
        "open(out,'w').write(h.hexdigest()+'\\n')\n"
        "sys.exit(int(os.environ.get('M39R2_EXIT','0')))\n")

class B2(Box):
    def __init__(s):
        Box.__init__(s); r = s.r; os.makedirs(os.path.join(r, "inp", "sub"))
        for n, t in (("a.csv", "id,v\n1,10\n"), ("b.csv", "id,v\n2,20\n"), ("hidden.csv", "x\n"), ("sub/c.csv", "id,v\n3,30\n")):
            open(os.path.join(r, "inp", n), "w").write(t)
        open(os.path.join(r, "bin", "readfile.py"), "w").write(READ)
        open(os.path.join(r, "bin", "helper.py"), "w").write("SALT='v1'\n")
        s.cl()  # authoring fix before any teeth run (disclosed): the default reader claim file was never written
    def rd(s, cmd, out="reports/r.txt", extra=(), ok_exit=None):
        return s.rec(SCR, [out], ["bin/readfile.py"] + cmd + [out], extra=extra, ok_exit=ok_exit)
    def cl(s, outs=("reports/r.txt",), order=True, gaps=None, name="cr.json"):
        c = {"schema": "solaris.delivery-claims/1", "contributions": [{"role": SCR, "outputs": list(outs)}]}
        if gaps is not None: c["contributions"][0]["accept_gaps"] = gaps
        if order: c["order"] = "order.json"
        json.dump(c, open(os.path.join(s.r, name), "w")); return name
    def go(s, name="cr.json"):
        rc, j, e = s.verify(name); return rc, j.get("verdict"), states(j).get(SCR), "Traceback" in e
def w(b, rel, t, mode="w"): open(b.p(*rel.split("/")), mode).write(t)
def nolines(b):
    try: return len(b.lines())
    except OSError: return 0

def bound(setup, mutate, cmd, extra=()):
    """record a reader, check GO, mutate, check the verdict; True when the change makes the claim not GO"""
    b = B2(); b.order()
    if setup: setup(b)
    k = b.rd(cmd(b) if callable(cmd) else cmd, extra=extra); g0 = b.go(); mutate(b); g1 = b.go(); b.close()
    return (k[0] == 0 and g0[1] == "GO" and g1[1] != "GO" and g1[0] == 1, (k[0], g0[:3], g1[:3]))

@safe
def c01():
    res = {}
    res["positional_file_change_not_go"] = bound(None, lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"), ["inp/a.csv"])
    res["flag_then_value_change_not_go"] = bound(None, lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"), ["--src", "inp/a.csv"])
    res["flag_equals_value_change_not_go"] = bound(None, lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"), ["--src=inp/a.csv"])
    res["positional_folder_file_added_not_go"] = bound(None, lambda b: w(b, "inp/new.csv", "id,v\n9,9\n"), ["inp"])
    res["absolute_path_inside_root_change_not_go"] = bound(None, lambda b: w(b, "inp/a.csv", "id,v\n1,11\n"), lambda b: [b.p("inp", "a.csv")])
    def sl(b): os.symlink("a.csv", b.p("inp", "link.csv"))
    b = B2(); b.order(); sl(b); k = b.rd(["inp/link.csv"]); g0 = b.go(); w(b, "inp/a.csv", "id,v\n1,11\n"); g1 = b.go(); b.close()
    res["symlink_named_refused_or_target_change_not_go"] = (k[0] == 2 or (k[0] == 0 and g1[1] != "GO"), (k[0], g0[:3], g1[:3]))
    row("C01 explicit inputs named in the command are bound in every common spelling (positional, --flag VALUE, --flag=VALUE, a folder, an absolute path inside ROOT, a symlink)", all(v[0] for v in res.values()), res)

@safe
def c02():
    res = {}; I = ["--inputs", "inp"]
    res["declared_folder_file_changed_not_go"] = bound(None, lambda b: w(b, "inp/hidden.csv", "y\n"), [], extra=I)
    res["declared_folder_file_added_not_go"] = bound(None, lambda b: w(b, "inp/sub/d.csv", "z\n"), [], extra=I)
    res["declared_folder_file_removed_not_go"] = bound(None, lambda b: os.remove(b.p("inp", "b.csv")), [], extra=I)
    res["declared_folder_file_renamed_not_go"] = bound(None, lambda b: os.rename(b.p("inp", "b.csv"), b.p("inp", "b2.csv")), [], extra=I)
    def tosym(b):
        shutil.copy(b.p("inp", "a.csv"), b.p("a.copy")); os.remove(b.p("inp", "a.csv")); os.symlink(b.p("a.copy"), b.p("inp", "a.csv"))
    res["declared_file_replaced_by_identical_symlink_not_go"] = bound(None, tosym, [], extra=I)
    res["declared_helper_module_changed_not_go"] = bound(None, lambda b: w(b, "bin/helper.py", "SALT='v2'\n"), [], extra=["--inputs", "inp", "bin/helper.py"])
    # restore byte for byte returns GO
    b = B2(); b.order(); b.rd([], extra=I); t = open(b.p("inp", "a.csv")).read(); w(b, "inp/a.csv", "q"); g1 = b.go(); w(b, "inp/a.csv", t); g2 = b.go(); b.close()
    res["restored_input_go_again"] = (g1[1] == "NO_GO" and g2[1] == "GO", (g1[:3], g2[:3]))
    # symlink inside a declared folder at record time: refused before running, or bound to its target
    b = B2(); b.order(); os.symlink("a.csv", b.p("inp", "sub", "ln.csv")); n0 = nolines(b); k = b.rd([], extra=I); n1 = nolines(b)
    g0 = b.go(); w(b, "inp/a.csv", "id,v\n1,99\n"); g1 = b.go(); b.close()
    res["symlink_inside_declared_folder_refused_or_bound"] = ((k[0] == 2 and n1 == n0) or (k[0] == 0 and g1[1] != "GO"), (k[0], n1 - n0, g0[:3], g1[:3]))
    # bad --inputs: refused with exit 2 before anything runs, nothing appended
    for nm, val in (("missing", ["inp/nope.csv"]), ("symlink", ["inp/sl"]), ("absolute", None), ("dotdot", ["../x"]), ("ledger_dir", [".delivery"])):
        b = B2(); b.order(); os.symlink("a.csv", b.p("inp", "sl")); n0 = nolines(b)
        k = b.rd(["inp/a.csv"], out="reports/bad.txt", extra=["--inputs"] + (val if val else [b.p("inp")])); ran = os.path.exists(b.p("reports", "bad.txt"))
        res["bad_inputs_%s_exit_2_nothing_run_or_appended" % nm] = (k[0] == 2 and not ran and nolines(b) == n0 and "Traceback" not in k[2], (k[0], ran, nolines(b) - n0, k[2].strip()[-120:]))
        b.close()
    row("C02 indirect inputs declared with --inputs: change, add, remove, rename, symlink swap and a helper module all leave GO; a restore returns GO; bad --inputs are refused before running", all(v[0] for v in res.values()), res)

@safe
def c03():
    res = {}
    def snapbox():
        b = Box(); b.full(); g0 = b.verify(); return b, g0
    def chk(name, mut, want=None):
        b, g0 = snapbox(); fs = sorted(os.listdir(b.p("snapshots", "s1"))); mut(b, fs); rc, j, e = b.verify(); st = states(j).get(DBA); b.close()
        res[name] = (g0[1].get("verdict") == "GO" and j.get("verdict") == "NO_GO" and rc == 1 and (want is None or st in want), (g0[1].get("verdict"), j.get("verdict"), st, fs))
    chk("member_removed_not_go", lambda b, fs: os.remove(b.p("snapshots", "s1", fs[0])), ("stale",))
    chk("member_renamed_not_go", lambda b, fs: os.rename(b.p("snapshots", "s1", fs[0]), b.p("snapshots", "s1", fs[0] + ".bak")))
    chk("member_added_not_go", lambda b, fs: open(b.p("snapshots", "s1", "extra.txt"), "w").write("x"), ("not_covered",))
    chk("member_added_in_new_nested_folder_not_go", lambda b, fs: (os.makedirs(b.p("snapshots", "s1", "n", "m")), open(b.p("snapshots", "s1", "n", "m", "x"), "w").write("x")))
    chk("output_folder_deleted_not_go", lambda b, fs: shutil.rmtree(b.p("snapshots", "s1")))
    chk("output_folder_emptied_not_go", lambda b, fs: [os.remove(b.p("snapshots", "s1", f)) for f in fs if os.path.isfile(b.p("snapshots", "s1", f))])
    def sym(b, fs):
        f = b.p("snapshots", "s1", fs[0]); shutil.copy(f, b.p("cp.bin")); os.remove(f); os.symlink(b.p("cp.bin"), f)
    chk("member_replaced_by_identical_symlink_not_go", sym)
    def swap(b, fs):
        a, c = b.p("snapshots", "s1", fs[0]), b.p("snapshots", "s1", fs[1]); os.rename(a, a + ".t"); os.rename(c, a); os.rename(a + ".t", c)
    chk("two_members_swapped_not_go", swap)
    b, g0 = snapbox(); fs = sorted(os.listdir(b.p("snapshots", "s1"))); keep = open(b.p("snapshots", "s1", fs[0]), "rb").read()
    os.remove(b.p("snapshots", "s1", fs[0])); g1 = b.verify(); open(b.p("snapshots", "s1", fs[0]), "wb").write(keep); g2 = b.verify(); b.close()
    res["removed_then_restored_go_again"] = (g1[1].get("verdict") == "NO_GO" and g2[1].get("verdict") == "GO", (g1[1].get("verdict"), g2[1].get("verdict")))
    row("C03 output-folder membership is complete: a member removed, renamed, added (also nested), swapped or replaced by a symlink, and the folder deleted or emptied, are all not GO; a restore returns GO", all(v[0] for v in res.values()), res)

@safe
def c04():
    res = {}
    for v in ("0,2", "0,1,2", "2", "1", "0,3", "0,255", "0,-2", "1,2"):
        b = B2(); b.order(); n0 = nolines(b); k = b.rd(["inp/a.csv"], ok_exit=v); ran = os.path.exists(b.p("reports", "r.txt")); b.close()
        res["ok_exit_%s_refused_exit_2_not_run" % v.replace(",", "_").replace("-", "m")] = (k[0] == 2 and not ran and nolines(b) == n0, (k[0], ran))
    os.environ["M39R2_EXIT"] = "2"; ENV["M39R2_EXIT"] = "2"
    try:
        b = B2(); b.order(); k = b.rd(["inp/a.csv"], ok_exit="0,1"); g = b.go(); g2 = b.go(b.cl(gaps=True, name="cg.json")); b.close()
    finally:
        ENV.pop("M39R2_EXIT", None); os.environ.pop("M39R2_EXIT", None)
    res["tool_exit_2_under_0_1_never_go_even_with_accept_gaps"] = (k[0] == 1 and g[1] == "NO_GO" and g2[1] == "NO_GO" and g[0] == 1, (k[0], g[:3], g2[:3]))
    ENV["M39R2_EXIT"] = "1"
    try:
        b = B2(); b.order(); k0 = b.rd(["inp/a.csv"]); g0 = b.go(); b.close()
        b = B2(); b.order(); k = b.rd(["inp/a.csv"], ok_exit="0,1"); g = b.go(); g2 = b.go(b.cl(gaps=True, name="cg.json")); b.close()
    finally:
        ENV.pop("M39R2_EXIT", None)
    res["exit_1_default_ok_exit_not_go"] = (k0[0] == 1 and g0[1] == "NO_GO", (k0[0], g0[:3]))
    res["exit_1_accepted_without_accept_gaps_not_go"] = (k[0] == 0 and g[1] == "NO_GO" and g[0] == 1, (k[0], g[:3]))
    res["exit_1_with_accept_gaps_is_go_with_gaps_not_go"] = (g2[1] == "GO_WITH_GAPS", g2[:3])
    row("C04 exit honesty: --ok-exit outside 0 or 0,1 is refused before running; a tool exit 2 never counts, even with accept_gaps; exit 1 is never a plain GO", all(v[0] for v in res.values()), res)

@safe
def q05():
    det = {}
    # undeclared indirect inputs (documented limit): the command neither names nor declares them
    b = B2(); b.order(); b.rd(["--quiet"]); w(b, "inp/hidden.csv", "changed\n"); det["undeclared_indirect_file_changed_verdict"] = b.go()[1]
    w(b, "bin/helper.py", "SALT='v9'\n"); det["undeclared_imported_helper_changed_verdict"] = b.go()[1]; b.close()
    b = B2(); b.order(); b.rd([], extra=["--inputs", "inp"]); os.makedirs(b.p("inp", "emptydir")); det["declared_folder_empty_subfolder_added_verdict"] = b.go()[1]; b.close()
    b, = (Box(),); b.full(); os.makedirs(b.p("snapshots", "s1", "emptydir")); det["output_folder_empty_subfolder_added_verdict"] = b.verify()[1].get("verdict"); b.close()
    # an input rewritten while the command runs: recorded after the run, is it surfaced?
    b = B2(); b.order()
    open(b.p("bin", "mut.py"), "w").write("import sys\nopen('inp/a.csv','a').write('9,9\\n')\nopen(sys.argv[-1],'w').write('done\\n')\n")
    k = b.rec(SCR, ["reports/r.txt"], ["bin/mut.py", "inp/a.csv", "reports/r.txt"]); rc, j, e = b.verify("cr.json") if os.path.exists(b.p("cr.json")) else b.verify(b.cl())
    det["input_rewritten_during_run"] = [k[0], j.get("verdict"), json.loads(b.lines()[-1]).get("inputs_changed_during_run")]; b.close()
    # verify exit codes per verdict
    ENV["M39R2_EXIT"] = "1"
    try:
        b = B2(); b.order(); b.rd(["inp/a.csv"], ok_exit="0,1"); det["verify_exit_GO_WITH_GAPS"] = b.go(b.cl(gaps=True, name="cg.json"))[:2]; b.close()
    finally:
        ENV.pop("M39R2_EXIT", None)
    b = B2(); b.rd(["inp/a.csv"]); det["verify_exit_EVIDENCED_NO_ORDER"] = b.go(b.cl(order=False, name="cn.json"))[:2]; b.close()
    # consistent full rewrite: a record that says exit 2 and ok true (doc limit for the chain; semantic check?)
    b = B2(); b.order(); b.rd(["inp/a.csv"]); recs = [json.loads(l) for l in b.lines()]; recs[-1].update(exit=2, ok_exit=[0, 1, 2], ok=True); b.rewrite(recs)
    det["rewritten_record_exit_2_ok_true_verdict"] = b.go()[:3]; b.close()
    row("Q05 OBS: undeclared indirect inputs, empty subfolders, an input rewritten during the run, verify exit codes per verdict, a rewritten exit-2 record (recorded, not scored)", True, det)

for f in (c01, c02, c03, c04, q05): f()
json.dump({"tool": TOOL, "python": sys.version.split()[0], "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
core = [r for r in ROWS if r["row"].startswith("C") or "crash" in r["row"]]; n = sum(r["pass"] for r in core)
print("M39R2 CONTRACT %d/%d core %s" % (n, len(core), "PASS" if n == len(core) else "FAIL"))
