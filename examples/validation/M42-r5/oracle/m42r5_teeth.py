"""M42 r5 teeth (Grok self-validation, not independent review). Each case edits plan.json in a fresh clone of HEAD
(uncommitted, so DIRTY_TREE is expected alongside) and runs daily_integration.py check without --run; the r5 change
is load-bearing only if removing or reverting it brings the named finding back. Usage: python3 m42r5_teeth.py REPO"""
import json, os, shutil, subprocess, sys, tempfile
R = os.path.abspath(sys.argv[1]); PLAN = "examples/capabilities/G42/plan.json"; T = "employees/quality-security/assurance/daily_integration.py"
HEAD = subprocess.run(["git", "-C", R, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
R5 = ["employees/quality-security/qa-engineer/host-portability.md", "employees/quality-security/qa-engineer/host_portability.py",
      "examples/capabilities/G40/README.md", "examples/capabilities/G40/portability_oracle.py", "tests/test_g40_capability.py",
      "employees/design/technical-writer/SKILL.md"]
def case(name, edit, want, info=False):
    t = tempfile.mkdtemp(prefix="m42t-"); d = os.path.join(t, "r")
    subprocess.run(["git", "clone", "-q", R, d], check=True)
    subprocess.run(["git", "-c", "advice.detachedHead=false", "-C", d, "checkout", "-q", "--detach", HEAD], check=True, capture_output=True)
    p = json.load(open(os.path.join(d, PLAN)))
    if edit: edit(p); open(os.path.join(d, PLAN), "w").write(json.dumps(p, indent=1) + "\n")
    out = os.path.join(t, "o.json")
    r = subprocess.run([sys.executable, T, "check", "--plan", PLAN, "--out", out], cwd=d, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    rep = json.load(open(out)) if os.path.exists(out) else {}
    f = rep.get("findings", [])
    codes = sorted(set(x["code"] for x in f)); det = sorted(x.get("detail", "")[:90] for x in f if x["code"] in want)
    ok = (r.returncode == 0 and not codes) if not want else (r.returncode == 1 and set(want) <= set(codes))
    if info:  # documents a limit, not a tooth: expect the finding to be absent
        ok = not (set(info) & set(codes))
    print("%s %s: rc=%d codes=%s %s" % ("PASS" if ok else "FAIL", name, r.returncode, codes, det if det else ""))
    shutil.rmtree(t); return ok
def drop(paths): return lambda p: p.__setitem__("resolved_overlaps", [o for o in p["resolved_overlaps"] if o["path"] not in paths])
def pin(gid, c): return lambda p: [q.__setitem__("commit", c) for q in p["prerequisites"] if q["id"] == gid]
res = [case("control (HEAD as committed)", None, []),
       case("the 6 r5 G40/G41 resolved overlaps removed", drop(R5), ["OVERLAP"]),
       case("only the technical-writer SKILL.md entry removed", drop(R5[-1:]), ["OVERLAP"]),
       case("G40 pinned back to r4 eabf69a", pin("G40", "eabf69ac9cf4f539bc39482b75681bf75e6e97e5"), ["DRIFT"]),
       case("G39 pinned back to r3 9ab3562 (r3 blobs equal the G40/G41 copies, so no overlap masks it)",
            pin("G39", "9ab356256d5147c89c0f780d4ab639c584971326"), ["DRIFT"]),
       # limit (P4 OBS): a path named in resolved_overlaps is not compared with any blob, so pinning G39 back to r4
       # (whose three blobs also differ from the G40/G41 r3 copies) gives no DRIFT; plan test, probe H1 and the
       # overlap audit cover the stale pin instead. Expect DRIFT absent here.
       case("LIMIT: G39 pinned back to r4 97d3d05 gives no DRIFT (resolved overlaps are not content-checked)",
            pin("G39", "97d3d05d92daa452c3eab668aa821fafd0d25bfa"), ["DIRTY_TREE"], info=["DRIFT"])]
print("TEETH %d/%d as expected" % (sum(res), len(res)))
