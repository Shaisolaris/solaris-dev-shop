#!/usr/bin/env python3
"""M40 oracle (Grok self-validation, not independent review). Written from M40.md, G40.md, docs/install.md and the
host_portability.py docstring before reading the builder's portability_oracle.py. Drives the real CLI on private
copies. A rows are scored; wheel rows (A05-A08) are scored only where this interpreter can build a wheel offline
(setuptools importable, 3.10+), otherwise they are recorded as skipped observations. O rows are observations.
Usage: PY m40_oracle.py SRC OUT.json"""
import json, os, runpy, shutil, subprocess, sys, tempfile, zipfile
SRC = os.path.abspath(sys.argv[1]); OUT = sys.argv[2]; PY = sys.executable; ROWS = []
T = "employees/quality-security/qa-engineer/host_portability.py"
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PIP_NO_INDEX="1", PIP_NO_BUILD_ISOLATION="0", PIP_DISABLE_PIP_VERSION_CHECK="1")
try:
    import setuptools  # noqa
    CAN_WHEEL = sys.version_info >= (3, 10)
except ImportError:
    CAN_WHEEL = False
def row(name, ok, det, scored=True):
    sub = {k: bool(v[0]) for k, v in det.items() if isinstance(v, (tuple, list)) and len(v) == 2 and isinstance(v[0], bool)}
    ROWS.append({"row": name, "pass": bool(ok), "sub": sub, "detail": det, "scored": scored})
    print(("PASS " if ok else "FAIL ") + name[:100] + " " + json.dumps(det, default=str)[:500], flush=True)
def safe(fn):
    def g():
        try: fn()
        except Exception as e: row(fn.__name__ + " crash", False, {"crash": repr(e)[:300]})
    return g
def copy():
    d = tempfile.mkdtemp(prefix="m40o-"); c = os.path.join(d, "repo")
    shutil.copytree(SRC, c, ignore=shutil.ignore_patterns(".git", "__pycache__", "build", "*.egg-info")); return d, c
def run(c, *a, cwd=None):
    p = subprocess.run([PY, os.path.join(c, T)] + list(a), cwd=cwd or tempfile.gettempdir(), capture_output=True, text=True, env=ENV, timeout=400)
    return p.returncode, p.stdout, p.stderr
def listing(c): return sorted(os.path.relpath(os.path.join(d, f), c) for d, ds, fs in os.walk(c) for f in fs + ds)
def js(o):
    try: return json.loads(o)
    except ValueError: return {}

@safe
def a01():
    d, c = copy(); res = {}; before = listing(c); rc, o, e = run(c, "python-bounds", c, "--json"); j = js(o)
    n = sum(1 for dd, ds, fs in os.walk(os.path.join(c, "employees")) for f in fs if f.endswith(".py"))
    res["exit_0"] = (rc == 0, rc)
    res["requires_python_from_pyproject"] = (j.get("requires_python") == ">=3.10", j.get("requires_python"))
    res["wheel_3_10_source_3_9"] = (j.get("wheel_and_installer") == "3.10+" and j.get("source_tools") == "3.9+", (j.get("wheel_and_installer"), j.get("source_tools")))
    res["every_employee_script_parsed"] = (j.get("scripts_parsed") == n and not j.get("scripts_failed"), (j.get("scripts_parsed"), n))
    res["interpreter_reported"] = (j.get("interpreter") == "%d.%d.%d" % sys.version_info[:3], j.get("interpreter"))
    res["no_file_written_in_repo"] = (listing(c) == before, len(set(listing(c)) - set(before)))
    # unseen failure: a 3.10-only construct in an employee script fails to parse on 3.9 and passes on 3.10+
    open(os.path.join(c, "employees", "quality-security", "qa-engineer", "zz_probe.py"), "w").write("match 1:\n    case 1:\n        pass\n")
    rc2, o2, e2 = run(c, "python-bounds", c, "--json"); j2 = js(o2); bad = [f.get("path") for f in j2.get("scripts_failed") or []]
    if sys.version_info < (3, 10):
        res["py310_syntax_reported_on_3_9"] = (rc2 == 1 and any("zz_probe" in b for b in bad), (rc2, bad))
    else:
        res["py310_syntax_parses_on_3_10_plus"] = (rc2 == 0 and not bad, (rc2, bad))
    shutil.rmtree(d)
    row("A01 python-bounds: requires-python and the 3.10+/3.9+ split are reported truthfully, every employee script is parsed, nothing is written, a 3.10-only script is caught on 3.9", all(v[0] for v in res.values()), res)

@safe
def a02():
    d, c = copy(); res = {}; dest = os.path.join(d, "host")
    rc, o, e = run(c, "skill-copy", c, "quality-security/qa-engineer", "--dest", dest, "--json"); j = js(o); miss = [m["ref"] for m in j.get("missing") or []]
    res["lone_qa_engineer_copy_broken_exit_1"] = (rc == 1 and j.get("status") == "broken", (rc, j.get("status")))
    res["names_missing_standard_and_assurance"] = (any("QUALITY-SECURITY-STANDARD.md" in m for m in miss) and any("assurance" in m for m in miss), miss[:8])
    res["copy_really_made"] = (os.path.isfile(os.path.join(dest, "qa-engineer", "SKILL.md")), dest)
    # recovery: put the referenced shared files next to the copy (as a complete bundle would) and re-check by hand
    ok = all(os.path.exists(os.path.normpath(os.path.join(dest, "qa-engineer", m))) is False for m in miss)
    res["missing_paths_really_missing_in_copy"] = (ok, len(miss))
    for nm, role in (("dotdot", "../x"), ("absolute", "/etc"), ("missing", "quality-security/nope"), ("no_contract", "creative-media")):
        rc2, o2, e2 = run(c, "skill-copy", c, role, "--dest", os.path.join(d, "h2"))
        res["bad_role_%s_exit_2" % nm] = (rc2 == 2 and "Traceback" not in e2, (rc2, e2.strip()[-100:]))
    rc3, o3, e3 = run(c, "skill-copy", os.path.join(d, "nope"), "quality-security/qa-engineer"); res["bad_repo_exit_2"] = (rc3 == 2, rc3)
    shutil.rmtree(d)
    row("A02 skill-copy: a lone qa-engineer copy is broken (exit 1) and names the shared standard and assurance paths it lost; bad roles and repos exit 2", all(v[0] for v in res.values()), res)

@safe
def a03():
    d, c = copy(); res = {}; out = os.path.join(d, "r.json")
    rc, o, e = run(c, "python-bounds", c, "--json", "--out", out); res["out_written_equals_stdout"] = (rc == 0 and js(open(out).read()) == js(o), rc)
    rc, o, e = run(c, "python-bounds", c, "--out", os.path.join(d, "no", "r.json")); res["out_missing_folder_exit_2_nothing"] = (rc == 2 and not os.path.exists(os.path.join(d, "no")), rc)
    rc, o, e = run(c, "python-bounds", os.path.join(d, "nope")); res["bad_repo_exit_2"] = (rc == 2 and "Traceback" not in e, rc)
    shutil.rmtree(d)
    row("A03 --out is written atomically and equals the JSON report; a missing --out folder or a bad repo exits 2 with nothing written", all(v[0] for v in res.values()), res)

@safe
def a04():
    res = {}; ns = runpy.run_path(os.path.join(SRC, T)); f = ns["inspect_wheel_names"]
    good = ["solaris_intake/__init__.py", "solaris_intake/control_plane/policy.json", "solaris_intake/control_plane/meta_control_plane.py"]
    codes = lambda n: sorted(x["code"] for x in f(n))
    res["clean_names_no_findings"] = (codes(good) == [], codes(good))
    res["pyc_found"] = ("wheel_contains_pyc" in codes(good + ["solaris_intake/__pycache__/x.cpython-312.pyc"]), 0)
    res["employees_found"] = ("wheel_ships_employees" in codes(good + ["employees/x/SKILL.md"]), 0)
    res["missing_policy_found"] = ("wheel_missing_control_plane" in codes(good[:1] + good[2:]), 0)
    res["checkout_layout_found"] = ("wheel_checkout_layout" in codes(good + ["x/control-plane/policy.json"]), 0)
    row("A04 wheel member inspection flags bytecode, employee skills, a missing control-plane policy and checkout layout, and passes a clean member list", all(v[0] for v in res.values()), res)

def wheel_rows():
    if not CAN_WHEEL:
        d, c = copy(); o = os.path.join(d, "out"); rc, so, e = run(c, "wheel-smoke", c, "--outside", o)
        det = {"skipped": "no offline wheel build on this interpreter (%s; needs 3.10+ and setuptools importable)" % sys.version.split()[0], "exit": rc, "stderr_tail": e.strip()[-160:], "outside_created": os.path.exists(o)}
        if sys.version_info < (3, 10):
            res = {"py39_wheel_smoke_exit_2_names_3_10": (rc == 2 and "3.10" in e, rc), "py39_nothing_created": (not os.path.exists(o), os.path.exists(o))}
            row("A09 on 3.9 wheel-smoke refuses with exit 2, names 3.10+, and creates nothing", all(v[0] for v in res.values()), res)
        row("O05 wheel rows A05-A08 skipped on this interpreter (recorded, not scored)", True, det, scored=False); shutil.rmtree(d); return
    d, c = copy(); o = os.path.join(d, "out"); before = listing(c); rc, so, e = run(c, "wheel-smoke", c, "--outside", o, "--json"); j = js(so); res = {}
    res["exit_0_pass"] = (rc == 0 and j.get("result") == "pass", (rc, j.get("result"), e.strip()[-120:]))
    res["employees_not_in_wheel"] = (j.get("employees_in_wheel") is False, j.get("employees_in_wheel"))
    whl = [os.path.join(o, "wheels", x) for x in os.listdir(os.path.join(o, "wheels"))] if os.path.isdir(os.path.join(o, "wheels")) else []
    names = zipfile.ZipFile(whl[0]).namelist() if whl else []
    res["wheel_really_built_with_policy"] = ("solaris_intake/control_plane/policy.json" in names, len(names))
    ex = os.path.join(o, "venv", "bin", "solaris-intake"); r = subprocess.run([ex, "self-test"], capture_output=True, text=True, cwd=d) if os.path.exists(ex) else None
    res["installed_command_runs_outside"] = (r is not None and r.returncode == 0, r.returncode if r else None)
    row("A05 wheel-smoke clean control: a wheel is built, installed outside the checkout, its command runs, and it carries no employee skills", all(v[0] for v in res.values()), res)
    added = sorted(set(listing(c)) - set(before))
    row("A06 wheel-smoke never edits REPO (its docstring: Never edits REPO)", not added, {"repo_unchanged": (not added, added[:6])})
    os.makedirs(os.path.join(c, "build", "lib", "solaris_intake"), exist_ok=True); open(os.path.join(c, "build", "lib", "solaris_intake", "stale_leftover.py"), "w").write("X=1\n")
    o2 = os.path.join(d, "out2"); rc2, so2, e2 = run(c, "wheel-smoke", c, "--outside", o2, "--json"); j2 = js(so2)
    w2 = [os.path.join(o2, "wheels", x) for x in os.listdir(os.path.join(o2, "wheels"))] if os.path.isdir(os.path.join(o2, "wheels")) else []
    st = [n for n in (zipfile.ZipFile(w2[0]).namelist() if w2 else []) if "stale" in n]
    res = {"stale_build_not_packed_or_reported": ((not st and rc2 == 0) or (st and j2.get("result") != "pass"), (rc2, j2.get("result"), st))}
    row("A07 a stale build/lib left in REPO is neither packed into the smoked wheel nor passed silently", all(v[0] for v in res.values()), res)
    o3 = os.path.join(c, "inside-out"); rc3, so3, e3 = run(c, "wheel-smoke", c, "--outside", o3)
    res = {"outside_inside_checkout_refused_exit_2": (rc3 == 2 and not os.path.exists(o3), (rc3, os.path.exists(o3)))}
    row("A08 --outside inside the checkout is refused (the smoke claims an install outside the checkout)", all(v[0] for v in res.values()), res)
    shutil.rmtree(d)

for fn in (a01, a02, a03, a04, safe(wheel_rows)): fn()
json.dump({"python": sys.version.split()[0], "can_wheel": CAN_WHEEL, "rows": ROWS}, open(OUT, "w"), indent=1, default=str)
core = [r for r in ROWS if r.get("scored", True)]; n = sum(r["pass"] for r in core)
print("M40 ORACLE %d/%d scored %s" % (n, len(core), "PASS" if n == len(core) else "FAIL"))
