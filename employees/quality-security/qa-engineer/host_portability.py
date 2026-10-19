#!/usr/bin/env python3
"""host_portability.py: fresh install and host skill-copy boundaries (G40).

  host_portability.py wheel-smoke REPO [--outside DIR] [--json]
  host_portability.py skill-copy REPO ROLE [--dest DIR] [--json]
  host_portability.py python-bounds REPO [--json]
  host_portability.py report REPO [--out FILE] [--json]

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
2 invalid input (nothing written). --out is written atomically. Python 3.9+, standard library
plus the pip/wheel already available to the interpreter. Never edits REPO.
"""
from __future__ import annotations

import argparse
import json
import os
import py_compile
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
    pass


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

def wheel_smoke(root, outside=None):
    """Mirror .github/workflows/ci.yml wheel build and outside-checkout smoke."""
    root = _repo(root)
    req = _requires_python(root)
    py = sys.version_info
    if (py.major, py.minor) < (3, 10):
        raise Invalid("wheel-smoke needs Python 3.10+ to build and install the wheel (this interpreter is %d.%d); source tools still run on 3.9+" % (py.major, py.minor))
    findings = []
    work = Path(outside) if outside else Path(tempfile.mkdtemp(prefix="g40-wheel-"))
    work.mkdir(parents=True, exist_ok=True)
    wheels = work / "wheels"
    venv = work / "venv"
    wheels.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    # build
    b = subprocess.run([sys.executable, "-m", "pip", "wheel", str(root), "--no-deps", "--wheel-dir", str(wheels)],
                       capture_output=True, text=True, env=env, timeout=300)
    if b.returncode != 0:
        raise Invalid("pip wheel failed: %s" % ((b.stderr or b.stdout)[-400:]))
    whls = sorted(wheels.glob("*.whl"))
    if len(whls) != 1:
        raise Invalid("expected one wheel, found %d" % len(whls))
    wheel = whls[0]
    names = []
    with zipfile.ZipFile(wheel) as zf:
        names = zf.namelist()
        findings.extend(inspect_wheel_names(names))
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
    root = _repo(root)
    role, src = _role_dir(root, role)
    dest_root = Path(dest) if dest else Path(tempfile.mkdtemp(prefix="g40-skill-"))
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
            py_compile.compile(str(p), doraise=True)
            parse_ok.append(p.relative_to(root).as_posix())
        except py_compile.PyCompileError as ex:
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


def report(root, outside=None):
    root = _repo(root)
    parts = {}
    # python bounds always
    parts["python_bounds"] = python_bounds(root)
    # skill-copy of qa-engineer (known external refs)
    parts["skill_copy_qa_engineer"] = skill_copy(root, "quality-security/qa-engineer")
    # wheel smoke only on 3.10+
    if sys.version_info >= (3, 10):
        parts["wheel_smoke"] = wheel_smoke(root, outside=outside)
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
    w = sub.add_parser("wheel-smoke"); w.add_argument("repo"); w.add_argument("--outside"); w.add_argument("--json", action="store_true"); w.add_argument("--out")
    s = sub.add_parser("skill-copy"); s.add_argument("repo"); s.add_argument("role"); s.add_argument("--dest"); s.add_argument("--json", action="store_true"); s.add_argument("--out")
    p = sub.add_parser("python-bounds"); p.add_argument("repo"); p.add_argument("--json", action="store_true"); p.add_argument("--out")
    r = sub.add_parser("report"); r.add_argument("repo"); r.add_argument("--outside"); r.add_argument("--json", action="store_true"); r.add_argument("--out")
    ns = ap.parse_args(argv)
    try:
        if ns.cmd == "wheel-smoke":
            out = wheel_smoke(ns.repo, ns.outside)
        elif ns.cmd == "skill-copy":
            out = skill_copy(ns.repo, ns.role, ns.dest)
        elif ns.cmd == "python-bounds":
            out = python_bounds(ns.repo)
        else:
            out = report(ns.repo, ns.outside)
        text = json.dumps(out, indent=2, sort_keys=True) + "\n"
        if ns.out:
            _atomic(ns.out, text)
    except Invalid as ex:
        print("invalid: %s. Nothing was written." % ex, file=sys.stderr)
        return 2
    print(text if ns.json else render(out), end="" if ns.json else "\n")
    return 0 if out.get("result") in ("pass", "skipped") and out.get("status", "complete") != "broken" else 1


if __name__ == "__main__":
    sys.exit(main())
