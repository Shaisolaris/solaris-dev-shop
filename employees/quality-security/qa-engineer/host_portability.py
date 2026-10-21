#!/usr/bin/env python3
"""host_portability.py: fresh install and host skill-copy boundaries (G40).

  host_portability.py wheel-smoke REPO [--outside DIR] [--wheelhouse DIR] [--json]
  host_portability.py skill-copy REPO ROLE [--dest DIR] [--json]
  host_portability.py python-bounds REPO [--json]
  host_portability.py report REPO [--outside DIR] [--wheelhouse DIR] [--out FILE] [--json]

What it checks, reading and running only local packaging commands:
- wheel-smoke: build a wheel from REPO (as .github/workflows/ci.yml does), install it into a
  temporary environment outside the checkout, run solaris-intake self-test / intake / skills,
  and confirm the wheel carries control-plane files under solaris_intake/control_plane/ and
  does not ship employee skill directories or .pyc files.
- skill-copy: copy only employees/ROLE into a destination and report which contract references
  and preflight targets still resolve. A lone copied skill folder that references a department
  standard outside itself is incomplete (status broken).
- python-bounds: report requires-python from pyproject.toml (wheel/installer: 3.10+) and that
  stdlib source tools under employees/ parse on the current interpreter (source tools: 3.9+).

Exit codes: 0 pass / complete report; 1 findings (smoke failed or skill-copy broken);
2 invalid input or failed build (nothing written, or only the named work folder). --out is written atomically. Python 3.9+, standard library
plus the pip/wheel already available to the interpreter. Never edits REPO: wheel-smoke builds from a private copy
under its work folder (build/, dist/, *.egg-info, caches and bytecode skipped) and refuses an --outside folder at or
under REPO, or one that exists and is not empty (it never deletes or overwrites there); a wheel member with no source
file is a finding (wheel_member_not_in_source).

Build backend: `pip wheel` installs the backend named in pyproject.toml (setuptools>=61) into an isolated build
environment, from the package index. Offline, pass --wheelhouse DIR: a folder holding a setuptools>=61 wheel (for
example the one bundled in Python 3.11's ensurepip/_bundled). The build then runs with --no-index --find-links DIR and
needs no network. A --wheelhouse that is missing or holds no setuptools>=61 wheel is refused before anything is
written. When the backend cannot be obtained, the error says so (build_backend_unavailable) and names --wheelhouse.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

SCHEMA = "solaris.host-portability/1"
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}


class Invalid(Exception):
    """Refused or failed run. `left` names the only folder the run wrote to, when it got that far."""
    def __init__(self, msg, left=None):
        super().__init__(msg)
        self.left = left


def _atomic(out, data):
    out = Path(out)
    if not out.parent.is_dir():
        raise Invalid("--out folder does not exist: %s" % out.parent.as_posix())
    fd, tmp = tempfile.mkstemp(dir=str(out.parent), prefix="." + out.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, str(out))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _repo(root):
    root = Path(root).resolve()
    if not root.is_dir():
        raise Invalid("REPO is not a directory")
    if not (root / "pyproject.toml").is_file():
        raise Invalid("REPO has no pyproject.toml")
    if not (root / "control-plane" / "meta_control_plane.py").is_file():
        raise Invalid("REPO has no control-plane/meta_control_plane.py")
    return root


def _requires_python(root):
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^requires-python\s*=\s*"([^"]+)"', text)
    if not m:
        raise Invalid("pyproject.toml has no requires-python")
    return m.group(1)



def inspect_wheel_names(names):
    """Findings from wheel member names alone (used by wheel-smoke and tests)."""
    findings = []
    if any(n.endswith(".pyc") for n in names):
        findings.append({"code": "wheel_contains_pyc", "detail": "wheel ships bytecode"})
    if any("/control-plane/" in n for n in names):
        findings.append({"code": "wheel_checkout_layout", "detail": "wheel uses checkout control-plane/ paths"})
    if "solaris_intake/control_plane/policy.json" not in names:
        findings.append({"code": "wheel_missing_control_plane", "detail": "policy.json not under solaris_intake/control_plane/"})
    if any(n.startswith("employees/") for n in names):
        findings.append({"code": "wheel_ships_employees", "detail": "wheel contains employee skill paths"})
    return findings

def _check_outside(root, outside):
    """--outside must be outside the checkout and new or empty: wheel-smoke never deletes or overwrites there."""
    work = Path(outside)
    wr = Path(os.path.realpath(str(work)))
    if wr == root or root in wr.parents:
        raise Invalid("--outside must be a folder outside the checkout")
    if work.exists() or work.is_symlink():
        if not work.is_dir():
            raise Invalid("--outside %s exists and is not a folder; name a new or empty folder" % work)
        if any(work.iterdir()):
            raise Invalid("--outside %s already exists and is not empty; name a new or empty folder "
                          "(wheel-smoke never deletes or overwrites files there)" % work)
    return work


_SETUPTOOLS_WHL = re.compile(r"^setuptools-(\d+)(?:\.[^-]*)?-.*\.whl$")


def _check_wheelhouse(wheelhouse):
    """--wheelhouse must be a folder with a setuptools>=61 wheel; checked before anything is written."""
    if wheelhouse is None:
        return None
    wh = Path(wheelhouse)
    if not wh.is_dir():
        raise Invalid("--wheelhouse %s is not a folder; name a folder holding a setuptools>=61 wheel" % wh)
    ok = [p.name for p in sorted(wh.iterdir()) if _SETUPTOOLS_WHL.match(p.name) and int(_SETUPTOOLS_WHL.match(p.name).group(1)) >= 61]
    if not ok:
        raise Invalid("--wheelhouse %s holds no setuptools>=61 wheel (the build backend named in pyproject.toml); "
                      "add one, for example from Python 3.11's ensurepip/_bundled" % wh)
    return Path(os.path.realpath(str(wh)))


def _backend_unavailable(text):
    t = text or ""
    return ("installing build dependencies" in t or "build dependencies" in t) and "setuptools" in t


def wheel_smoke(root, outside=None, wheelhouse=None):
    """Mirror .github/workflows/ci.yml wheel build and outside-checkout smoke."""
    root = _repo(root)
    wh = _check_wheelhouse(wheelhouse)
    req = _requires_python(root)
    py = sys.version_info
    if (py.major, py.minor) < (3, 10):
        raise Invalid("wheel-smoke needs Python 3.10+ to build and install the wheel (this interpreter is %d.%d); source tools still run on 3.9+" % (py.major, py.minor))
    if outside:
        work = _check_outside(root, outside)
        work.mkdir(parents=True, exist_ok=True)
    else:
        work = Path(tempfile.mkdtemp(prefix="g40-wheel-"))
    try:
        return _wheel_smoke_in(root, req, work, wh)
    except Invalid as ex:
        raise Invalid(str(ex), left=work)


def _wheel_smoke_in(root, req, work, wh=None):
    findings = []
    # build from a private copy: pip/setuptools write build/ and *.egg-info next to the source, and a stale
    # build/lib left in REPO would be packed into the wheel. work is new or empty, so nothing is replaced.
    srcdir = work / "src"
    shutil.copytree(root, srcdir, ignore=shutil.ignore_patterns(*sorted(SKIP_DIRS), "*.egg-info", "*.pyc"))
    wheels = work / "wheels"
    venv = work / "venv"
    wheels.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    # build
    cmd = [sys.executable, "-m", "pip", "wheel", str(srcdir), "--no-deps", "--wheel-dir", str(wheels)]
    if wh is not None:
        cmd += ["--no-index", "--find-links", str(wh)]
    b = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=300)
    if b.returncode != 0:
        tail = (b.stderr or b.stdout)[-400:].strip()
        if _backend_unavailable(b.stderr or b.stdout):
            how = ("the --wheelhouse folder did not supply it" if wh is not None else
                   "the package index was not reachable or is disabled; offline, rerun with --wheelhouse DIR holding a setuptools>=61 wheel")
            raise Invalid("build_backend_unavailable: pip could not install the build backend setuptools>=61 named in "
                          "pyproject.toml (%s). pip said: %s" % (how, tail))
        raise Invalid("pip wheel failed: %s" % tail)
    whls = sorted(wheels.glob("*.whl"))
    if len(whls) != 1:
        raise Invalid("expected one wheel, found %d" % len(whls))
    wheel = whls[0]
    names = []
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        findings.extend(inspect_wheel_names(names))
        extra = [n for n in names if n.startswith("solaris_intake/") and not (
            (root / "solaris_intake" / n[len("solaris_intake/"):]).is_file() or
            (root / "control-plane" / n[len("solaris_intake/control_plane/"):]).is_file())]
        if extra:
            findings.append({"code": "wheel_member_not_in_source", "detail": ", ".join(sorted(extra)[:10])})
        if "solaris_intake/control_plane/policy.json" in names:
            packaged = zf.read("solaris_intake/control_plane/meta_control_plane.py")
            source = (root / "control-plane" / "meta_control_plane.py").read_bytes()
            if packaged != source:
                findings.append({"code": "wheel_control_plane_drift", "detail": "packaged meta_control_plane.py differs from source"})
    # install outside
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True, capture_output=True, env=env, timeout=120)
    pip = str(venv / "bin" / "pip")
    intake = str(venv / "bin" / "solaris-intake")
    i = subprocess.run([pip, "install", "--no-deps", str(wheel)], capture_output=True, text=True, env=env, timeout=180)
    if i.returncode != 0:
        findings.append({"code": "wheel_install_failed", "detail": (i.stderr or i.stdout)[-300:]})
    else:
        for args in (["self-test"], ["intake", "--explain", "review this code"], ["skills", "playwright", "--json"]):
            r = subprocess.run([intake] + args, cwd=str(work), capture_output=True, text=True, env=env, timeout=120)
            if r.returncode != 0:
                findings.append({"code": "smoke_failed", "detail": "solaris-intake %s rc=%d" % (" ".join(args), r.returncode)})
            elif args[0] == "skills":
                try:
                    data = json.loads(r.stdout)
                    ids = {item["id"] for item in data.get("skills", [])}
                    if "solaris.qa-engineer" not in ids:
                        findings.append({"code": "smoke_skills_missing", "detail": "solaris.qa-engineer not in skills search"})
                except ValueError:
                    findings.append({"code": "smoke_skills_unreadable", "detail": "skills --json was not JSON"})
    result = "pass" if not findings else "findings"
    return {
        "schema": SCHEMA, "command": "wheel-smoke", "result": result,
        "requires_python": req, "wheel": wheel.name, "outside": str(work),
        "build_backend_from": ("wheelhouse %s (--no-index)" % wh) if wh is not None else "package index or pip configuration",
        "wheel_files_sample": sorted([n for n in names if n.endswith((".py", ".json", ".md"))])[:12],
        "employees_in_wheel": any(n.startswith("employees/") for n in names),
        "findings": findings,
        "statement": "wheel install and intake smoke outside the checkout; employee skills are not in the wheel and need a full checkout or a complete skill bundle",
    }


def _role_dir(root, role):
    role = role.strip().strip("/")
    if not role or ".." in Path(role).parts or os.path.isabs(role):
        raise Invalid("ROLE must be a relative employees path like quality-security/qa-engineer")
    src = root / "employees" / role
    if not src.is_dir():
        raise Invalid("ROLE path does not exist under employees/: %s" % role)
    if not (src / "capability.contract.json").is_file():
        raise Invalid("ROLE has no capability.contract.json")
    return role, src


def skill_copy(root, role, dest=None):
    """Copy employees/ROLE and report missing references. Without --dest the copy goes to a temp folder that is
    removed again before returning (M40 P4-2: it used to stay in TMPDIR on every run)."""
    root = _repo(root)
    role, src = _role_dir(root, role)
    if dest:
        return _skill_copy(role, src, Path(dest))
    tmp = Path(tempfile.mkdtemp(prefix="g40-skill-"))
    try:
        rep = _skill_copy(role, src, tmp)
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
    rep["dest"] = None
    rep["temp_copy"] = "removed after the check; pass --dest DIR to keep the copy"
    return rep


def _skill_copy(role, src, dest_root):
    dest_root.mkdir(parents=True, exist_ok=True)
    target = dest_root / Path(role).name
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    contract = json.loads((target / "capability.contract.json").read_text(encoding="utf-8"))
    refs = list(contract.get("dependencies", {}).get("references", []) or [])
    checks = list((contract.get("dependencies", {}).get("preflight") or {}).get("checks", []) or [])
    resolved, missing = [], []
    for ref in refs:
        # only path-like refs
        if not isinstance(ref, str) or ref.startswith("http"):
            continue
        p = (target / ref)
        if p.exists():
            resolved.append({"ref": ref, "via": "reference"})
        else:
            missing.append({"ref": ref, "via": "reference"})
    for c in checks:
        if not isinstance(c, dict) or c.get("kind") != "file_exists":
            continue
        tgt = c.get("target")
        if not isinstance(tgt, str):
            continue
        p = target / tgt
        if p.exists():
            resolved.append({"ref": tgt, "via": "preflight:%s" % c.get("id", "")})
        else:
            missing.append({"ref": tgt, "via": "preflight:%s" % c.get("id", "")})
    # also surface ../ paths from SKILL.md / rules.md even if not in contract
    for name in ("SKILL.md", "rules.md"):
        f = target / name
        if not f.is_file():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        for m in re.finditer(r"(?:\.\./)+[A-Za-z0-9_./\-]+", text):
            ref = m.group(0)
            p = target / ref
            item = {"ref": ref, "via": name}
            if p.exists():
                if item not in resolved:
                    resolved.append(item)
            else:
                if item not in missing:
                    missing.append(item)
    status = "complete" if not missing else "broken"
    return {
        "schema": SCHEMA, "command": "skill-copy", "result": "pass" if status == "complete" else "findings",
        "role": role, "dest": str(target), "status": status,
        "copied_files": sum(1 for _ in target.rglob("*") if _.is_file()),
        "resolved": resolved, "missing": missing,
        "statement": "a lone copied skill folder is incomplete when references or preflight targets escape it; keep the full checkout or copy every referenced shared standard",
    }


def python_bounds(root):
    root = _repo(root)
    req = _requires_python(root)
    # sample stdlib employee scripts (depth-limited)
    scripts = []
    for p in sorted((root / "employees").rglob("*.py")):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        scripts.append(p)
        if len(scripts) >= 40:
            break
    parse_ok, parse_fail = [], []
    for p in scripts:
        try:
            compile(p.read_bytes(), str(p), "exec", dont_inherit=True)  # in memory: a check never writes bytecode
            parse_ok.append(p.relative_to(root).as_posix())
        except (SyntaxError, ValueError) as ex:
            parse_fail.append({"path": p.relative_to(root).as_posix(), "detail": str(ex)[:160]})
    wheel_min = "3.10+"
    source_min = "3.9+"
    findings = []
    if not req.replace(" ", "").startswith(">="):
        findings.append({"code": "requires_python_form", "detail": req})
    # document the split
    return {
        "schema": SCHEMA, "command": "python-bounds", "result": "pass" if not parse_fail else "findings",
        "requires_python": req, "wheel_and_installer": wheel_min, "source_tools": source_min,
        "interpreter": "%d.%d.%d" % sys.version_info[:3],
        "scripts_parsed": len(parse_ok), "scripts_failed": parse_fail,
        "findings": findings,
        "statement": "wheel and installer need Python 3.10+ (requires-python); source checkout capability tools use the stdlib and run on 3.9+",
    }


def report(root, outside=None, wheelhouse=None):
    root = _repo(root)
    _check_wheelhouse(wheelhouse)  # refuse before skill-copy or anything else runs
    if outside and sys.version_info >= (3, 10):
        _check_outside(root, outside)
    parts = {}
    # python bounds always
    parts["python_bounds"] = python_bounds(root)
    # skill-copy of qa-engineer (known external refs)
    parts["skill_copy_qa_engineer"] = skill_copy(root, "quality-security/qa-engineer")
    # wheel smoke only on 3.10+
    if sys.version_info >= (3, 10):
        parts["wheel_smoke"] = wheel_smoke(root, outside=outside, wheelhouse=wheelhouse)
    else:
        parts["wheel_smoke"] = {
            "schema": SCHEMA, "command": "wheel-smoke", "result": "skipped",
            "detail": "interpreter %d.%d < 3.10; run wheel-smoke on 3.10+" % sys.version_info[:2],
            "statement": "wheel smoke skipped on this interpreter",
        }
    findings = []
    for k, v in parts.items():
        if v.get("result") == "findings":
            findings.extend({"where": k, **f} if isinstance(f, dict) else {"where": k, "detail": f}
                            for f in v.get("findings") or v.get("missing") or [])
    result = "pass" if not findings and parts.get("wheel_smoke", {}).get("result") in ("pass", "skipped") else "findings"
    if parts.get("skill_copy_qa_engineer", {}).get("status") == "broken" and result == "pass":
        result = "findings"
    return {
        "schema": SCHEMA, "command": "report", "result": result,
        "parts": parts, "findings_count": len(findings),
        "statement": "install and host portability boundaries for the wheel vs source checkout vs lone skill copy",
    }


def render(r):
    lines = ["host portability: %s (%s)" % (r.get("result"), r.get("command"))]
    if r.get("command") == "skill-copy":
        lines.append("skill-copy %s: %s (%d missing)" % (r.get("role"), r.get("status"), len(r.get("missing") or [])))
        for m in r.get("missing") or []:
            lines.append("  MISSING %s (%s)" % (m["ref"], m["via"]))
    if r.get("command") == "python-bounds":
        lines.append("wheel/installer %s; source tools %s; requires-python %s; interpreter %s" % (
            r.get("wheel_and_installer"), r.get("source_tools"), r.get("requires_python"), r.get("interpreter")))
    if r.get("command") == "wheel-smoke":
        lines.append("wheel %s; employees_in_wheel=%s; findings=%d" % (
            r.get("wheel"), r.get("employees_in_wheel"), len(r.get("findings") or [])))
        for f in r.get("findings") or []:
            lines.append("  FINDING %s %s" % (f.get("code"), f.get("detail", "")))
    if r.get("command") == "report":
        lines.append("parts: %s" % ", ".join("%s=%s" % (k, v.get("result") or v.get("status")) for k, v in (r.get("parts") or {}).items()))
    if r.get("statement"):
        lines.append(r["statement"])
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="fresh install and host skill-copy boundaries")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("wheel-smoke"); w.add_argument("repo"); w.add_argument("--outside"); w.add_argument("--wheelhouse"); w.add_argument("--json", action="store_true"); w.add_argument("--out")
    s = sub.add_parser("skill-copy"); s.add_argument("repo"); s.add_argument("role"); s.add_argument("--dest"); s.add_argument("--json", action="store_true"); s.add_argument("--out")
    p = sub.add_parser("python-bounds"); p.add_argument("repo"); p.add_argument("--json", action="store_true"); p.add_argument("--out")
    r = sub.add_parser("report"); r.add_argument("repo"); r.add_argument("--outside"); r.add_argument("--wheelhouse"); r.add_argument("--json", action="store_true"); r.add_argument("--out")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "wheel-smoke":
            out = wheel_smoke(ns.repo, ns.outside, ns.wheelhouse)
        elif ns.cmd == "skill-copy":
            out = skill_copy(ns.repo, ns.role, ns.dest)
        elif ns.cmd == "python-bounds":
            out = python_bounds(ns.repo)
        else:
            out = report(ns.repo, ns.outside, ns.wheelhouse)
        text = json.dumps(out, indent=2, sort_keys=True) + "\n"
        if ns.out:
            _atomic(ns.out, text)
    except Invalid as ex:
        if getattr(ex, "left", None):
            print("invalid: %s. Files were written only under the work folder %s (left for inspection); "
                  "the checkout and everything else were not changed." % (ex, ex.left), file=sys.stderr)
        else:
            print("invalid: %s. Nothing was written." % ex, file=sys.stderr)
        return 2
    print(text if ns.json else render(out), end="" if ns.json else "\n")
    return 0 if out.get("result") in ("pass", "skipped") and out.get("status", "complete") != "broken" else 1


if __name__ == "__main__":
    sys.exit(main())
