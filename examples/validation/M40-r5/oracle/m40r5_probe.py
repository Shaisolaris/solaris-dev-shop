"""M40 r5 probe (Grok self-validation): offline reproduction of G40 wheel-smoke (M40 P3-2).
Usage: python m40r5_probe.py CHECKOUT WHEELHOUSE OUT.json. Every case runs offline (PIP_NO_INDEX=1, no PIP_* config)."""
import json, os, subprocess, sys, tempfile, shutil, zipfile
from pathlib import Path
wt, wh, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
TOOL = wt / "employees/quality-security/qa-engineer/host_portability.py"
ENV = {k: v for k, v in os.environ.items() if not k.startswith("PIP_") and k != "G40_WHEELHOUSE"}
ENV.update(PIP_NO_INDEX="1", PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONDONTWRITEBYTECODE="1")
NEW = sys.version_info >= (3, 10)
res = []
def run(*a):
    p = subprocess.run([sys.executable, str(TOOL)] + [str(x) for x in a], capture_output=True, text=True, env=ENV, timeout=600)
    return p.returncode, p.stdout, p.stderr
def case(name, ok, note):
    res.append({"case": name, "ok": bool(ok), "note": note}); print("%s %s %s" % ("PASS" if ok else "FAIL", name, note))
tmp = Path(tempfile.mkdtemp(prefix="m40r5-"))
try:
    if NEW:
        w = tmp / "c1"; rc, o, e = run("wheel-smoke", wt, "--outside", w, "--wheelhouse", wh, "--json")
        try: j = json.loads(o)
        except ValueError: j = {}
        whl = list((w / "wheels").glob("*.whl"))
        names = zipfile.ZipFile(whl[0]).namelist() if whl else []
        case("C1 offline wheelhouse build passes", rc == 0 and j.get("result") == "pass" and str(j.get("build_backend_from", "")).startswith("wheelhouse")
             and len(whl) == 1 and not any(n.startswith("employees/") for n in names) and "solaris_intake/control_plane/policy.json" in names,
             "rc=%s result=%s from=%s" % (rc, j.get("result"), j.get("build_backend_from")))
        w = tmp / "c2"; rc, o, e = run("wheel-smoke", wt, "--outside", w, "--json")
        case("C2 offline no wheelhouse names backend and remedy", rc == 2 and "build_backend_unavailable" in e and "--wheelhouse" in e and str(w) in e,
             "rc=%s msg=%s" % (rc, e.strip()[:160]))
        bad = tmp / "corrupt"; bad.mkdir(); (bad / "setuptools-80.0.0-py3-none-any.whl").write_bytes(b"not a zip")
        w = tmp / "c7"; rc, o, e = run("wheel-smoke", wt, "--outside", w, "--wheelhouse", bad, "--json")
        case("C7 corrupt setuptools wheel fails with exit 2, no traceback from the tool", rc == 2 and "Traceback (most recent call last):\n  File \"%s" % TOOL not in e,
             "rc=%s backend_named=%s" % (rc, "build_backend_unavailable" in e))
    old = tmp / "old"; old.mkdir(); (old / "setuptools-60.10.0-py3-none-any.whl").write_bytes(b"x")
    w = tmp / "c3"; rc, o, e = run("wheel-smoke", wt, "--outside", w, "--wheelhouse", old)
    case("C3 setuptools<61 wheelhouse refused, nothing written", rc == 2 and not w.exists() and "Nothing was written" in e, "rc=%s exists=%s" % (rc, w.exists()))
    txt = tmp / "txt"; txt.mkdir(); (txt / "setuptools-80.0.0.txt").write_text("x")
    w = tmp / "c4"; rc, o, e = run("wheel-smoke", wt, "--outside", w, "--wheelhouse", txt)
    case("C4 non-wheel file named setuptools refused", rc == 2 and not w.exists(), "rc=%s" % rc)
    f = tmp / "afile"; f.write_text("keep")
    w = tmp / "c5"; rc, o, e = run("wheel-smoke", wt, "--outside", w, "--wheelhouse", f)
    case("C5 wheelhouse that is a file refused and kept", rc == 2 and f.read_text() == "keep" and not w.exists(), "rc=%s" % rc)
    td = Path(tempfile.gettempdir()); before = {p.name for p in td.glob("g40-skill-*")}
    w = tmp / "c6"; rc, o, e = run("report", wt, "--outside", w, "--wheelhouse", old)
    after = {p.name for p in td.glob("g40-skill-*")}
    case("C6 report refuses bad wheelhouse before skill-copy runs", rc == 2 and after == before and not w.exists(), "rc=%s new_skill_dirs=%d" % (rc, len(after - before)))
    st = subprocess.run(["git", "-C", str(wt), "status", "--porcelain"], capture_output=True, text=True).stdout
    case("C8 checkout unchanged", st.strip() == "", "dirty=%d" % len(st.splitlines()))
finally:
    shutil.rmtree(tmp, ignore_errors=True)
n = sum(r["ok"] for r in res)
out.write_text(json.dumps({"python": sys.version.split()[0], "checkout_head": subprocess.run(["git", "-C", str(wt), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip(), "cases": res}, indent=2) + "\n")
print("M40R5 PROBE %d/%d" % (n, len(res)))
sys.exit(0 if n == len(res) else 1)
