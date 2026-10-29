#!/usr/bin/env python3
"""G40 oracle: host portability tool checked by effects (wheel, skill-copy, python bounds).

  python3 portability_oracle.py [--tool PATH]

Expectations are derived here. A tool that always says pass, skips the outside install, or
claims a lone skill copy is complete fails. Prints ACCEPTED n/n or REJECTED k/n.
"""
import argparse, json, os, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TOOL = REPO / "employees/quality-security/qa-engineer/host_portability.py"
ENV = dict({name: os.environ[name] for name in (
               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
               'GITHUB_ACTIONS',
           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE="1")
PY = sys.executable
# offline reproduction: a folder holding a setuptools==84.2.1 wheel, passed to wheel-smoke --wheelhouse
WHEELHOUSE = []


def run(tool, *args, timeout=300):
    p = subprocess.run([PY, str(tool)] + [str(a) for a in args], capture_output=True, text=True, env=ENV, timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def js(tool, *args):
    rc, o, e = run(tool, *args, "--json")
    try:
        return rc, json.loads(o)
    except ValueError:
        return rc, None


def o1_skill_copy_broken(tool):
    """Lone qa-engineer copy must be broken (missing ../ standards)."""
    d = Path(tempfile.mkdtemp(prefix="g40o1-"))
    try:
        rc, j = js(tool, "skill-copy", REPO, "quality-security/qa-engineer", "--dest", d)
        miss = {m["ref"] for m in (j or {}).get("missing", [])}
        ok = rc == 1 and j and j.get("status") == "broken" and any("QUALITY-SECURITY-STANDARD" in x for x in miss)
        return ok, "skill-copy broken with standard missing; rc=%s status=%s missing=%s" % (rc, (j or {}).get("status"), sorted(miss)[:3])
    finally:
        shutil.rmtree(d, ignore_errors=True)


def o2_full_checkout_role_ok(tool):
    """References that live inside the role folder resolve when the role is still in the checkout (python-bounds / report path)."""
    rc, j = js(tool, "python-bounds", REPO)
    ok = rc == 0 and j and j.get("result") == "pass" and j.get("wheel_and_installer") == "3.10+" and j.get("source_tools") == "3.9+"
    return ok, "python-bounds wheel 3.10+ / source 3.9+; rc=%s req=%s" % (rc, (j or {}).get("requires_python"))


def o3_wheel_smoke(tool):
    if sys.version_info < (3, 10):
        return True, "wheel-smoke skipped on %d.%d (not scored)" % sys.version_info[:2]
    outside = Path(tempfile.mkdtemp(prefix="g40o3-"))
    try:
        rc, j = js(tool, "wheel-smoke", REPO, "--outside", outside, *WHEELHOUSE)
        ok = (rc == 0 and j and j.get("result") == "pass" and j.get("employees_in_wheel") is False
              and not j.get("findings") and str(j.get("wheel", "")).endswith(".whl"))
        return ok, "wheel-smoke outside checkout; rc=%s employees_in_wheel=%s findings=%s" % (
            rc, (j or {}).get("employees_in_wheel"), (j or {}).get("findings"))
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def o4_wheel_omits_employees(tool):
    if sys.version_info < (3, 10):
        return True, "skipped on <3.10"
    outside = Path(tempfile.mkdtemp(prefix="g40o4-"))
    try:
        rc, j = js(tool, "wheel-smoke", REPO, "--outside", outside, *WHEELHOUSE)
        if not j or not j.get("wheel"):
            return False, "no wheel name"
        base = Path(j["outside"]) if j.get("outside") else outside
        whls = list(base.glob("wheels/*.whl"))
        if not whls:
            whls = list(base.glob("**/*.whl"))
        if not whls:
            return False, "wheel file missing on disk"
        with zipfile.ZipFile(whls[0]) as zf:
            names = zf.namelist()
        ok = not any(n.startswith("employees/") for n in names) and "solaris_intake/control_plane/policy.json" in names
        return ok, "wheel names omit employees/; has control_plane policy; n=%d" % len(names)
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def o5_invalid_repo(tool):
    d = Path(tempfile.mkdtemp(prefix="g40o5-"))
    try:
        rc, o, e = run(tool, "python-bounds", d)
        ok = rc == 2 and "Nothing was written" in e and "Traceback" not in e + o
        return ok, "empty dir -> exit 2 clean; rc=%s" % rc
    finally:
        shutil.rmtree(d, ignore_errors=True)


def o6_invalid_role(tool):
    rc, o, e = run(tool, "skill-copy", REPO, "../etc")
    ok = rc == 2 and "Nothing was written" in e
    return ok, "bad ROLE -> exit 2; rc=%s" % rc


def o7_report_names_broken_copy(tool):
    outside = Path(tempfile.mkdtemp(prefix="g40o7-"))
    try:
        args = ["report", REPO, "--outside", outside] + WHEELHOUSE
        rc, j = js(tool, *args)
        part = (j or {}).get("parts", {}).get("skill_copy_qa_engineer") or {}
        ok = j and part.get("status") == "broken" and rc == 1
        return ok, "report marks qa-engineer skill-copy broken; rc=%s status=%s" % (rc, part.get("status"))
    finally:
        shutil.rmtree(outside, ignore_errors=True)


def o8_out_missing_folder(tool):
    missing = Path(tempfile.mkdtemp(prefix="g40o8-")) / "no" / "report.json"
    shutil.rmtree(missing.parent.parent)
    rc, o, e = run(tool, "python-bounds", REPO, "--out", missing)
    ok = rc == 2 and "Nothing was written" in e and "Traceback" not in e
    return ok, "missing --out folder -> exit 2; rc=%s" % rc


CHECKS = [
    ("o1", o1_skill_copy_broken),
    ("o2", o2_full_checkout_role_ok),
    ("o3", o3_wheel_smoke),
    ("o4", o4_wheel_omits_employees),
    ("o5", o5_invalid_repo),
    ("o6", o6_invalid_role),
    ("o7", o7_report_names_broken_copy),
    ("o8", o8_out_missing_folder),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tool", type=Path, default=TOOL); ap.add_argument("--only")
    ap.add_argument("--wheelhouse", default=os.environ.get("G40_WHEELHOUSE") or None,
                    help="offline: folder with a setuptools==84.2.1 wheel, passed to wheel-smoke (default $G40_WHEELHOUSE)")
    ns = ap.parse_args()
    if ns.wheelhouse:
        WHEELHOUSE[:] = ["--wheelhouse", ns.wheelhouse]
    only = set(ns.only.split(",")) if ns.only else None
    passed = 0; total = 0
    for name, fn in CHECKS:
        if only and name not in only:
            continue
        total += 1
        try:
            ok, note = fn(ns.tool)
        except Exception as ex:
            ok, note = False, "oracle error: %s" % ex
        print("%s %s %s" % ("PASS" if ok else "FAIL", name, note))
        passed += 1 if ok else 0
    print("%s %d/%d" % ("ACCEPTED" if passed == total else "REJECTED", passed, total))
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
