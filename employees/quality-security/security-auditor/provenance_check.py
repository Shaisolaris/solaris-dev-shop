#!/usr/bin/env python3
"""Repository license and artifact-integrity consistency, from the files as they are.

  provenance_check.py check ROOT [--manifest FILE] [--exclude DIR ...] [--json] [--out FILE]

Checks, reading only:
- the root LICENSE is recognised from its text (MIT or Apache-2.0 fingerprints); anything else is reported
  as unrecognised and nothing is guessed;
- every license declaration agrees with it: pyproject.toml `license`, each employees/**/plugin.json
  `license`, the README license badge and `## License` section;
- NOTICE.md lists every other LICENSE* file in the tree, and every LICENSE path it lists exists;
- with --manifest ("<sha256>  <relative path>" lines): every listed file exists and has that digest, hashed
  by G05's artifact_digests (no symlinks, no paths outside ROOT). The output carries the digests as a G05
  subject binding.
--exclude DIR leaves a folder (for example a test fixture that is its own synthetic repository) out of the
license walk; the report lists every excluded folder and the license files found under it, so nothing is
silently hidden.

What a clean result means: the declarations are consistent with each other and with the files, and the
listed bytes are the bytes on disk. It is not a legal opinion on licence compatibility, ownership or
obligations, and it authenticates no one: an author or approver named in plain text stays a claim.

Exit codes: 0 consistent; 1 findings; 2 invalid input (unreadable ROOT, malformed manifest), nothing written.
--out is written atomically. Python 3.9+, standard library; never runs or edits the files it reads.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

G05 = Path(__file__).resolve().parents[1] / "assurance" / "quality_os.py"
SCHEMA = "solaris.provenance-check/1"
FINGERPRINTS = {
    "MIT": ("permission is hereby granted, free of charge, to any person obtaining a copy",
            "the above copyright notice and this permission notice shall be included",
            'the software is provided "as is", without warranty of any kind'),
    "Apache-2.0": ("apache license", "version 2.0, january 2004", "terms and conditions for use, reproduction, and distribution"),
}
SPDX_ALIASES = {"mit": "MIT", "mit license": "MIT", "apache-2.0": "Apache-2.0", "apache 2.0": "Apache-2.0",
                "apache license 2.0": "Apache-2.0", "apache-2": "Apache-2.0"}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"}
MANIFEST_LINE = re.compile(r"^([0-9a-f]{64}) [ *](\S.*)$")


class Invalid(Exception):
    pass


def _g05():
    spec = importlib.util.spec_from_file_location("g05_quality_os", str(G05))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m  # dataclasses in quality_os.py need the module registered
    keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True  # read-only: leave no cache beside G05
    try:
        spec.loader.exec_module(m)
    finally:
        sys.dont_write_bytecode = keep
    return m


def _norm(s):
    return " ".join(s.replace("\u201c", '"').replace("\u201d", '"').split()).casefold()


def identify(text):
    t = _norm(text)
    hits = [k for k, phr in FINGERPRINTS.items() if all(p in t for p in phr)]
    return hits[0] if len(hits) == 1 else None


def spdx(v):
    if not isinstance(v, str):
        return None
    return SPDX_ALIASES.get(_norm(v), v.strip())


def _read(p):
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _walk(root, top=None, excluded=()):
    top = top or root
    for dp, dns, fns in os.walk(str(root)):
        keep = []
        for d in sorted(dns):
            rel = (Path(dp) / d).relative_to(top).as_posix()
            if d not in SKIP_DIRS and rel not in excluded:
                keep.append(d)
        dns[:] = keep
        for f in sorted(fns):
            yield Path(dp) / f


def _is_license(p):
    return p.name.upper().startswith(("LICENSE", "LICENCE", "COPYING"))


def check(root, manifest=None, exclude=()):
    root = Path(root)
    if not root.is_dir():
        raise Invalid("ROOT is not a directory")
    ex = []
    for e in exclude:
        e = e.strip("/")
        if not e or os.path.isabs(e) or ".." in Path(e).parts or not (root / e).is_dir():
            raise Invalid("--exclude %r must be a folder inside ROOT" % e[:80])
        ex.append(Path(e).as_posix())
    ex = tuple(sorted(set(ex)))
    F, decl = [], []
    lic_text = _read(root / "LICENSE")
    actual = identify(lic_text) if lic_text is not None else None
    if lic_text is None:
        F.append({"code": "license_missing", "path": "LICENSE", "detail": "no readable root LICENSE file"})
    elif actual is None:
        F.append({"code": "license_unrecognized", "path": "LICENSE", "detail": "text matches no known license fingerprint; not guessed"})

    def declared(path, value, how):
        v = spdx(value)
        decl.append({"path": path, "declared": v, "how": how})
        if v is None:
            F.append({"code": "license_undeclared", "path": path, "detail": "%s has no license value" % how})
        elif actual is not None and v != actual:
            F.append({"code": "license_mismatch", "path": path, "detail": "%s says %s, LICENSE is %s" % (how, v, actual)})

    py = _read(root / "pyproject.toml")
    if py is not None:
        m = re.search(r'(?m)^license\s*=\s*(?:\{\s*text\s*=\s*"([^"]*)"\s*\}|"([^"]*)")', py)
        declared("pyproject.toml", (m.group(1) or m.group(2)) if m else None, "pyproject license")
    for p in _walk(root / "employees", root, ex) if (root / "employees").is_dir() else []:
        if p.name != "plugin.json":
            continue
        rel = p.relative_to(root).as_posix()
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            F.append({"code": "plugin_unreadable", "path": rel}); continue
        declared(rel, d.get("license") if isinstance(d, dict) else None, "plugin.json license")
    rd = _read(root / "README.md")
    if rd is not None:
        for m in re.finditer(r"img\.shields\.io/badge/license-([A-Za-z0-9.]+)-", rd):
            declared("README.md", m.group(1).replace("--", "-"), "README badge")
        m = re.search(r"(?m)^## License\s*\n+\s*([A-Za-z0-9.\- ]+?)[.\n]", rd)
        if m:
            declared("README.md", m.group(1), "README License section")
    # NOTICE: other license files must be listed, listed ones must exist
    others = sorted(p.relative_to(root).as_posix() for p in _walk(root, root, ex) if _is_license(p) and p.parent != root)
    skipped = {e: sorted(p.relative_to(root).as_posix() for p in _walk(root / e, root) if _is_license(p)) for e in ex}
    notice = _read(root / "NOTICE.md")
    listed = set(re.findall(r"`([^`\s]*(?:LICEN[CS]E|COPYING)[^`\s]*)`", notice or "")) - {"LICENSE"}
    for o in others:
        if o not in listed:
            F.append({"code": "upstream_license_unlisted", "path": o, "detail": "license file not named in NOTICE.md"})
    for l in sorted(listed):
        if not (root / l).is_file():
            F.append({"code": "notice_path_missing", "path": "NOTICE.md", "detail": "lists %s, which does not exist" % l})
    integ = None
    if manifest is not None:
        integ = verify_manifest(root, manifest, F)
    return {"schema": SCHEMA, "result": "consistent" if not F else "findings", "license": actual or "unrecognized",
            "declarations": len(decl), "declared_values": sorted({str(x["declared"]) for x in decl}),
            "upstream_license_files": others, "excluded": skipped, "integrity": integ, "findings": F,
            "statement": "consistency of declarations and file digests only; not a legal opinion; no identity is authenticated"}


def verify_manifest(root, manifest, F):
    try:
        lines = Path(manifest).read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as ex:
        raise Invalid("manifest unreadable: %s" % ex.__class__.__name__)
    want = {}
    for n, line in enumerate(lines, 1):
        if not line.strip():
            continue
        m = MANIFEST_LINE.match(line)
        if not m:
            raise Invalid("manifest line %d is not '<sha256>  <path>'" % n)
        if m.group(2) in want:
            raise Invalid("manifest lists %s twice" % m.group(2))
        want[m.group(2)] = m.group(1)
    if not want:
        raise Invalid("manifest lists no files")
    g = _g05()
    got, ok = {}, 0
    for rel, h in want.items():
        if os.path.isabs(rel) or ".." in Path(rel).parts:
            F.append({"code": "artifact_refused", "path": rel, "detail": "manifest path must be relative inside ROOT"}); continue
        if not (root / rel).exists() and not (root / rel).is_symlink():
            F.append({"code": "artifact_missing", "path": rel}); continue
        try:
            d = g.artifact_digests(root, [rel])
        except ValueError as ex:
            F.append({"code": "artifact_refused", "path": rel, "detail": str(ex)[:160]}); continue
        if (root / rel).is_dir():
            F.append({"code": "artifact_refused", "path": rel, "detail": "manifest entries must be files"}); continue
        got[rel] = d[rel]
        if d[rel] != h:
            F.append({"code": "digest_mismatch", "path": rel, "detail": "file bytes differ from the manifest"})
        else:
            ok += 1
    return {"listed": len(want), "matching": ok, "subject": {"digests": got} if got else None}


def _atomic(out, data):
    out = Path(out)
    fd, tmp = tempfile.mkstemp(dir=str(out.parent), prefix="." + out.name + ".")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, str(out))
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def render(r):
    out = ["provenance check: %s; LICENSE %s; %d declaration(s) %s" % (r["result"], r["license"], r["declarations"], "/".join(r["declared_values"]))]
    if r["integrity"]:
        out.append("integrity: %d of %d listed file(s) match" % (r["integrity"]["matching"], r["integrity"]["listed"]))
    for f in r["findings"]:
        out.append("  FINDING %s %s%s" % (f["code"], f.get("path", ""), ": " + f["detail"] if f.get("detail") else ""))
    for e, lic in r["excluded"].items():
        out.append("excluded %s (license files there: %s)" % (e, ", ".join(lic) or "none"))
    out.append(r["statement"])
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="license and artifact-integrity consistency")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("root"); c.add_argument("--manifest"); c.add_argument("--exclude", action="append", default=[]); c.add_argument("--json", action="store_true"); c.add_argument("--out")
    ns = ap.parse_args(argv)
    try:
        r = check(ns.root, ns.manifest, ns.exclude)
    except Invalid as ex:
        print("invalid: %s. Nothing was written." % ex, file=sys.stderr)
        return 2
    text = json.dumps(r, indent=2, sort_keys=True)
    if ns.out:
        _atomic(ns.out, text + "\n")
    print(text if ns.json else render(r))
    return 0 if r["result"] == "consistent" else 1


if __name__ == "__main__":
    sys.exit(main())
