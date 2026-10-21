#!/usr/bin/env python3
"""Repository license and artifact-integrity consistency, from the files as they are.

  provenance_check.py check ROOT [--manifest FILE] [--exclude DIR ...] [--json] [--out FILE]

Checks, reading only:
- the root LICENSE is recognised from its whole text (MIT or Apache-2.0; fragments and added terms are not, including terms in a
  copyright line or the Apache appendix); anything else is reported as unrecognised and nothing is guessed;
- every license declaration agrees with it: pyproject.toml `license` (string, text, file or [project.license] table forms), every `plugin.json` under ROOT (including chief-of-staff/)
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

Exit codes: 0 consistent; 1 findings; 2 invalid input (unreadable ROOT, malformed manifest, --out folder missing or --out
is a folder), nothing written.
--out is written atomically. Python 3.9+, standard library; never runs or edits the files it reads.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import sys
import tempfile
from pathlib import Path

G05 = Path(__file__).resolve().parents[1] / "assurance" / "quality_os.py"
SCHEMA = "solaris.provenance-check/1"
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


MIT_TITLES = {"mit license", "the mit license", "the mit license (mit)", "mit"}
MIT_BODY = _norm("""Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction, including without
limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial portions of
the Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.""")
# sha256 of the normalised Apache-2.0 text from its title through "END OF TERMS AND CONDITIONS"
APACHE_TERMS_SHA = "95cef6332b35354c12f9d666ab9ff47002e6f7ef937924896882b2e0cdb7a0d6"
APACHE_END = "end of terms and conditions"
APACHE_APPENDIX = "appendix: how to apply the apache license to your work"
# The standard appendix is compared word for word; only its one boilerplate copyright line may differ (placeholder, or
# years and a holder). Both published bracket spellings are accepted: "{}" (common copies) and "[]" (apache.org).
# Generalised from the M38 r2 proposed patch (Grok self-validation), which matched one spelling by fixed-length hashes.
APPENDIX_PRE = _norm("""APPENDIX: How to apply the Apache License to your work. To apply the Apache License to your work,
attach the following boilerplate notice, with the fields enclosed by brackets "{}" replaced with your own identifying
information. (Don't include the brackets!) The text should be enclosed in the appropriate comment syntax for the file
format. We also recommend that a file or class name and description of purpose be included on the same "printed page"
as the copyright notice for easier identification within third-party archives. Copyright""")
APPENDIX_POST = _norm("""Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in
compliance with the License. You may obtain a copy of the License at http://www.apache.org/licenses/LICENSE-2.0 Unless
required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS"
BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language
governing permissions and limitations under the License.""")
# A copyright line is "copyright [(c)] YEAR[S] HOLDER[.] [all rights reserved.]" (M38 r2 P2-1). The holder may not hold a
# sentence (no . ; : ! ? inside) and may not use words that grant, limit or condition use; such a line is not dropped,
# so the text no longer matches. After the holder's first comma only a company suffix or "and contributors" may follow
# (M38 r3 P2-1: ", which cannot be resold"). This is a guard, not a parser: a restriction with no comma and none of these
# words could still pass, so the report lists every copyright line it set aside (license_copyright_lines) for a person.
YEARS = r"\d{4}(?:\s*[-,\u2013]\s*\d{4})*,?"
HOLDER_RE = re.compile(r"^(?P<h>[^.;:!?]{1,200}?)\.?(?: all rights reserved\.?)?$")
OPERATIVE = re.compile(r"\b(?:may|must|shall|not|no|only|unless|except\w*|prohibit\w*|forbid\w*|permi\w*|\w*commercial\w*"
                       r"|restrict\w*|licen[cs]\w*|terms?|conditions?|software|use[ds]?|usage|without|cannot|can't|never"
                       r"|allow\w*|resal\w*|resel\w*|resold|sell\w*|sold|purposes?|exclusive\w*|solely|redistribut\w*"
                       r"|distribut\w*|copy|copies|modif\w*)\b")
HOLDER_TAIL = re.compile(r"(?:inc|llc|ltd|gmbh|corp|co|plc|ag|sa|bv|and (?:its |other )?contributors|et al)")
COPYRIGHT_RE = re.compile(r"^(?:copyright(?: \(c\)| \u00a9)?|\(c\)|\u00a9) (?P<rest>" + YEARS + r" .+)$")
# M38 r4 P4-1: a company name that happens to hold a guard word ("Sellers Inc", "Copy Corp", "Never Settle GmbH") was
# unrecognised. Such a holder is set aside only when, in the line as written, it is one to four capitalised words
# followed by a company suffix and none of the strong restriction words below appear. A capitalised restriction that
# ends in a suffix and avoids them can still pass, so the line stays listed in license_copyright_lines for a person.
STRONG = re.compile(r"\b(?:may|must|shall|not|no|only|unless|except\w*|prohibit\w*|forbid\w*|permi\w*|\w*commercial\w*"
                    r"|restrict\w*|licen[cs]\w*|terms?|conditions?|use[ds]?|usage|without|cannot|can't|solely|exclusive\w*)\b")
COMPANY_RE = re.compile(r"[A-Z0-9][A-Za-z0-9&'-]*(?: [A-Z0-9][A-Za-z0-9&'-]*){0,3},? (?:Inc|LLC|Ltd|GmbH|Corp|Co|PLC|AG|SA|BV)")
COPYRIGHT_ORIG_RE = re.compile(r"^(?:copyright(?: \(c\)| \u00a9)?|\(c\)|\u00a9) " + YEARS
                               + r" (?P<h>[^.;:!?]{1,200}?)\.?(?: all rights reserved\.?)?$", re.I)


def _years_holder_ok(s):
    """'YEAR[S] HOLDER[.] [all rights reserved.]' with a plain holder name."""
    m = re.match("^" + YEARS + r" (.+)$", s)
    h = HOLDER_RE.match(m.group(1)) if m else None
    if not h or OPERATIVE.search(h.group("h")):
        return False
    # a holder is a name: after its first comma only company suffixes or "and contributors" may follow
    return all(HOLDER_TAIL.fullmatch(x.strip()) for x in h.group("h").split(",")[1:])


def _company_holder(line):
    """The line as written: a capitalised company name with a suffix and no strong restriction word (M38 r4 P4-1)."""
    m = COPYRIGHT_ORIG_RE.match(" ".join(line.split()))
    return bool(m) and bool(COMPANY_RE.fullmatch(m.group("h"))) and not STRONG.search(m.group("h").casefold())


def _copyright_line(s, line=None):
    m = COPYRIGHT_RE.match(s)
    if not m:
        return False
    return _years_holder_ok(m.group("rest")) or (line is not None and _company_holder(line))


def _appendix_ok(tail):
    if not tail:
        return True
    for o, c in ("{}", "[]"):
        pre = APPENDIX_PRE.replace('"{}"', '"%s%s"' % (o, c))
        if tail.startswith(pre + " ") and tail.endswith(" " + APPENDIX_POST):
            mid = tail[len(pre):len(tail) - len(APPENDIX_POST)].strip()
            if mid == "%syyyy%s %sname of copyright owner%s" % (o, c, o, c) or _years_holder_ok(mid):
                return True
    return False


def identify(text):
    """The whole text must be the license: a fragment, a header or added terms are not recognised (nothing guessed)."""
    return identify_detail(text)[0]


def identify_detail(text):
    """(license or None, the copyright lines set aside before comparing the MIT body)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if lines and _norm(lines[0]) in MIT_TITLES:
        lines.pop(0)
    dropped = []
    while lines and _copyright_line(_norm(lines[0]), lines[0]):
        dropped.append(lines.pop(0))
    if _norm(" ".join(lines)) == MIT_BODY:
        return "MIT", dropped
    t = _norm(text); j = t.find(APACHE_END)
    if j > 0 and hashlib.sha256(t[:j + len(APACHE_END)].encode("utf-8")).hexdigest() == APACHE_TERMS_SHA:
        tail = t[j + len(APACHE_END):].strip()
        if _appendix_ok(tail):
            return "Apache-2.0", []
    return None, []


_TOML_STR = r"""(?:"([^"\n]*)"|'([^'\n]*)')"""


def _pyproject_license(py):
    """The [project] license as ("text", value) or ("file", path): license = "X" or 'X', license = { text = .. } or
    { file = .. }, or a [project.license] table. ("text", None) when none is found. Not a full TOML parser."""
    def section(name):
        m = re.search(r"(?m)^\[\s*" + re.escape(name) + r"\s*\]\s*$", py)
        if not m:
            return None
        n = re.search(r"(?m)^\[", py[m.end():])
        return py[m.end():m.end() + n.start()] if n else py[m.end():]

    def keyval(body, key):
        m = re.search(r"(?:^|[\s{,])" + key + r"\s*=\s*" + _TOML_STR, body, re.M)
        return (m.group(1) if m.group(1) is not None else m.group(2)) if m else None

    proj = section("project")
    for body in ([proj] if proj is not None else []) + [py]:
        m = re.search(r"(?m)^license\s*=\s*(?:" + _TOML_STR + r"|\{([^}\n]*)\})", body)
        if m:
            if m.group(3) is None:
                return "text", m.group(1) if m.group(1) is not None else m.group(2)
            f = keyval(m.group(3), "file")
            return ("file", f) if f is not None else ("text", keyval(m.group(3), "text"))
        if proj is not None:
            break
    tab = section("project.license")
    if tab is not None:
        f = keyval(tab, "file")
        return ("file", f) if f is not None else ("text", keyval(tab, "text"))
    return "text", None


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
    actual, cr_lines = identify_detail(lic_text) if lic_text is not None else (None, [])
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
        kind, val = _pyproject_license(py)
        if kind == "file":
            lp = root / val
            if os.path.isabs(val) or ".." in Path(val).parts or not lp.is_file():
                F.append({"code": "license_undeclared", "path": "pyproject.toml",
                          "detail": "pyproject license file %r is not a file inside ROOT" % val[:80]})
            elif lp.resolve() == (root / "LICENSE").resolve():
                decl.append({"path": "pyproject.toml", "declared": actual or "LICENSE", "how": "pyproject license file"})
            else:
                other = identify(_read(lp) or "")
                declared("pyproject.toml", other or "unrecognized text in %s" % val[:80], "pyproject license file")
        else:
            declared("pyproject.toml", val, "pyproject license")
    for p in _walk(root, root, ex):
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
        # the name may be wrapped in one Markdown emphasis or code mark: **X**, __X__, *X*, _X_ or `X` (M38 r2 P4-3)
        m = re.search(r"(?m)^## License\s*\n+\s*(\*\*|__|\*|_|`)?([A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*(?:\s+[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*)*)"
                      r"(?(1)(?:\*\*|__|\*|_|`))(?=\s*[,.]|\s*$)", rd)
        if m:
            declared("README.md", m.group(2), "README License section")
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
            "license_copyright_lines": cr_lines,
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
    matching, ok = {}, 0
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
        if d[rel] != h:
            F.append({"code": "digest_mismatch", "path": rel, "detail": "file bytes differ from the manifest"})
        else:
            matching[rel] = d[rel]
            ok += 1
    return {"listed": len(want), "matching": ok, "subject": {"digests": matching} if matching else None}


def _atomic(out, data):
    out = Path(out)
    if not out.parent.is_dir():
        raise Invalid("--out folder does not exist: %s" % out.parent.as_posix())
    if out.is_dir():
        raise Invalid("--out names a folder, not a file: %s" % out.as_posix())
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
    for line in r.get("license_copyright_lines") or []:
        out.append("  LICENSE copyright line set aside before comparing (read it): %s" % line)
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
        text = json.dumps(r, indent=2, sort_keys=True)
        if ns.out:
            _atomic(ns.out, text + "\n")
    except Invalid as ex:
        print("invalid: %s. Nothing was written." % ex, file=sys.stderr)
        return 2
    print(text if ns.json else render(r))
    return 0 if r["result"] == "consistent" else 1


if __name__ == "__main__":
    sys.exit(main())
