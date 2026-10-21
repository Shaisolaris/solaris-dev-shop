#!/usr/bin/env python3
"""Conservative local project activation and resume for the project-onboarding skill.

Creates Scope/, Development/, Delivery/, Assets/, STATUS.md, Scope/ROUND-PLAN.md
and Delivery/CREDENTIALS.md (credential locations only) inside one project root,
and records a small journal (.solaris-activation.json) so an interrupted or
repeated activation resumes consistently.

What it never does: deploy, read or store secret values, contact a network,
install CI, set CI secrets, protect branches, create commits or branches, or
modify an existing Git repository. With --init-git it may run `git init` in a
project root that has no repository; the result is an unborn repository and the
first commit stays an owner step.

Python standard library only. Run `activate.py --help`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import socket
import stat
import subprocess
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

SCHEMA = "solaris.project-activation/1"
JOURNAL = ".solaris-activation.json"
LOCK = ".solaris-activation.lock"
FOLDERS = ("Scope", "Development", "Delivery", "Assets")
STATUS, PLAN, CREDS = "STATUS.md", "Scope/ROUND-PLAN.md", "Delivery/CREDENTIALS.md"
GENERATED = (STATUS, PLAN, CREDS)
PROJECT_TYPES = ("web app", "website", "mobile app", "desktop app", "game", "other")
LIMITS = {"name": 120, "project_type": 40, "deploy_model": 300, "brief": 500,
          "system": 80, "username": 120, "location": 300}
CREDENTIAL_KEYS = ("system", "username", "location")
EXTERNAL_OWNER_STEPS = ("Live deployment, CI secrets, branch protection, remote repository "
                        "creation and store submission are owner-approved steps; activation "
                        "performed none of them.")

# Recognizers for secret-shaped text. Matching is a guard, not proof: arbitrary
# text cannot be shown secret-free by pattern matching.
SECRET_PATTERNS: Tuple[Tuple[str, "re.Pattern[str]"], ...] = tuple(
    (label, re.compile(rx)) for label, rx in (
        ("GitHub token", r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"),
        ("AWS access key id", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        ("Slack token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
        ("API secret key", r"\bsk-[A-Za-z0-9_-]{20,}"),
        ("Google API key", r"\bAIza[0-9A-Za-z_-]{35}"),
        ("private key block", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
        ("JSON web token", r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),
        ("secret assignment", r"(?i)\b(?:password|passwd|pwd|secret|token|api[_-]?key)\s*[:=]\s*\S"),
        ("long opaque string", r"\b(?=[A-Za-z0-9+_=]*\d)(?=[A-Za-z0-9+_=]*[A-Za-z])[A-Za-z0-9+_=]{40,}\b"),
    ))


class ActivationError(Exception):
    """Raised for a refused activation. Carries the result to report."""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _lstat(path: Path) -> Optional[os.stat_result]:
    try:
        return os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None  # a non-directory ancestor is reported by the folder preflight


NAME_MAX = 255
ROOT_MAX = 900  # leaves room under the 1024-byte PATH_MAX for Scope/.ROUND-PLAN.md.<hex>.activation-tmp


def _path_problem(path: Path) -> Optional[str]:
    """Bounded check of a root path before touching it: component and total length."""
    for part in path.parts:
        if len(os.fsencode(part)) > NAME_MAX:
            return f"a path component is longer than {NAME_MAX} bytes"
    if len(os.fsencode(str(path))) > ROOT_MAX:
        return f"the path is longer than {ROOT_MAX} bytes"
    return None


def _kind(st: Optional[os.stat_result]) -> str:
    if st is None:
        return "missing"
    if stat.S_ISLNK(st.st_mode):
        return "symlink"
    if stat.S_ISDIR(st.st_mode):
        return "directory"
    if stat.S_ISREG(st.st_mode):
        return "file"
    return "other"


# ---------------------------------------------------------------------------
# Intake validation (before any write)
# ---------------------------------------------------------------------------

def _check_text(field: str, value: Any, problems: List[Dict[str, str]], required: bool) -> Optional[str]:
    if value is None:
        if required:
            problems.append({"field": field, "problem": "required"})
        return None
    if not isinstance(value, str):
        problems.append({"field": field, "problem": "must be text"})
        return None
    text = value.strip()
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in text):
        # Lone surrogates cannot be encoded to UTF-8; refuse before any write or render.
        problems.append({"field": field, "problem": "must not contain unpaired surrogate characters"})
        return None
    if not _visible(text):  # blank, zero-width, Hangul/braille fillers, combining marks alone
        if required:
            problems.append({"field": field, "problem": "must not be blank"})
        return None
    if any(ord(ch) < 32 or ord(ch) == 127 or ch in "\u2028\u2029" for ch in text):
        problems.append({"field": field, "problem": "must be a single line without control characters"})
        return None
    if len(text) > LIMITS[field.split(".")[-1]]:
        problems.append({"field": field, "problem": f"longer than {LIMITS[field.split('.')[-1]]} characters"})
        return None
    if not field.endswith("deploy_model") and DEPLOY_MARKER.search(text):
        # STATUS.md carries exactly one DEPLOY-MODEL line; other fields may not imitate it
        problems.append({"field": field, "problem": "must not contain a DEPLOY-MODEL: marker"})
        return None
    for label, rx in SECRET_PATTERNS:
        if rx.search(_without_commit_ids(text) if field == "brief" else text):
            # The value itself is never echoed.
            problems.append({"field": field, "problem": f"looks like a secret value ({label}); "
                             "record where the secret lives, not the secret"})
            return None
    return text


DEPLOY_MARKER = re.compile(r"(?i)deploy[-_ ]?model\s*:")
UNRESOLVED_ANSWER = re.compile(r"(?i)^unresolved\b")
COMMIT_ID = re.compile(r"(?i)\b(?:commit|fork|sha|revision|rev)\b[\s:#@-]*(?:of\s+)?([0-9a-f]{40}|[0-9a-f]{64})\b")


# Characters that leave no ink on the page but are not Cf/Cc/Z* (Hangul fillers, braille blank).
_BLANK_LOOKING = frozenset("ᅟᅠㅤﾠ⠀")


def _visible(text: str) -> bool:
    """True when text has at least one character that a reader can see.

    Whitespace, format/control marks (Cf/Cc/Z*), combining marks alone (Mn/Me),
    and known blank-looking fillers (Hangul fillers, braille blank) do not count.
    Ambiguous deploy answers therefore stay unresolved instead of finishing complete.
    """
    for ch in text:
        if ch.isspace() or ch in _BLANK_LOOKING:
            continue
        cat = unicodedata.category(ch)
        if cat in ("Cf", "Cc", "Zs", "Zl", "Zp", "Mn", "Me"):
            continue
        name = unicodedata.name(ch, "")
        if "FILLER" in name or name == "BRAILLE PATTERN BLANK":
            continue
        return True
    return False


def _answer_token(text: str) -> str:
    """Fold an answer so a disguised UNRESOLVED can be matched at its start.

    NFKD, then drop format, control and combining marks (zero-width joiners, accents put on letters), and turn every
    kind of space or blank-looking filler into one plain space. Spaces are kept, not deleted, so "UNRESOLVED ask the
    owner" still starts with the word UNRESOLVED and the word boundary in UNRESOLVED_ANSWER still holds.
    """
    out = []
    for ch in unicodedata.normalize("NFKD", text):
        cat = unicodedata.category(ch)
        if cat in ("Cf", "Cc", "Mn", "Me"):
            continue
        out.append(" " if ch.isspace() or ch in _BLANK_LOOKING or cat in ("Zs", "Zl", "Zp") else ch)
    return " ".join("".join(out).split())


# Cyrillic and Greek letters that look like the Latin letters of UNRESOLVED (and a few neighbours). Folding them only
# matters for the UNRESOLVED and placeholder checks, so a wrong fold can only ask the owner again (fail closed).
_CONFUSABLE = str.maketrans({
    "\u0430": "a", "\u0410": "A", "\u0435": "e", "\u0415": "E", "\u0451": "e", "\u0401": "E",
    "\u043e": "o", "\u041e": "O", "\u0440": "p", "\u0420": "P", "\u0441": "c", "\u0421": "C",
    "\u0443": "y", "\u0423": "Y", "\u0445": "x", "\u0425": "X", "\u0455": "s", "\u0405": "S",
    "\u0456": "i", "\u0406": "I", "\u0458": "j", "\u0408": "J", "\u0501": "d", "\u051b": "q",
    "\u041d": "H", "\u041c": "M", "\u0422": "T", "\u041a": "K", "\u0412": "B", "\u0432": "b",
    "\u0578": "n", "\u057d": "u", "\u0585": "o", "\u0274": "N", "\u0280": "R", "\u1d20": "V", "\u1d0f": "O",
    "\u03bf": "o", "\u039f": "O", "\u03b5": "e", "\u0395": "E", "\u03bd": "v", "\u039d": "N",
    "\u03c5": "u", "\u03a5": "Y", "\u03c1": "p", "\u03a1": "P", "\u0399": "I", "\u03b9": "i",
    "\u0391": "A", "\u03b1": "a", "\u0392": "B", "\u039a": "K", "\u039c": "M", "\u03a4": "T",
    "\u03a7": "X", "\u0396": "Z", "\u0397": "H", "\u0475": "v", "\u0474": "V",
})

# Answers that only hold a place for a later decision. They are no answer, the same as blank or UNRESOLVED.
PLACEHOLDER_ANSWERS = frozenset({
    "tbd", "tba", "tbc", "todo", "to do", "to be decided", "to be determined", "to be confirmed", "n a", "na",
    "none", "nothing", "unknown", "not sure", "unsure", "pending", "undecided", "later", "decide later",
    "ask owner", "ask the owner", "placeholder", "fill in", "fill me in", "xxx", "x", "null", "nil", "undefined",
})


def _placeholder(token: str) -> bool:
    """True when a folded answer is punctuation only (?, -, ..., n/a) or one of PLACEHOLDER_ANSWERS."""
    words = re.sub(r"[\W_]+", " ", token.lower()).split()
    return not words or " ".join(words) in PLACEHOLDER_ANSWERS


def _no_answer(text: str) -> bool:
    """An answer that starts with UNRESOLVED (also spelled with look-alike letters) or is only a placeholder."""
    token = _answer_token(text).translate(_CONFUSABLE)
    return bool(UNRESOLVED_ANSWER.match(token)) or _placeholder(token)


def _without_commit_ids(text: str) -> str:
    """A brief may name a Git commit (40 or 64 lowercase hex after a word like commit/fork/sha); that id is not a secret."""
    return COMMIT_ID.sub(lambda m: m.group(0)[: m.start(1) - m.start(0)] + "<commit-id>", text)


def normalize_intake(raw: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Dict[str, str]]]:
    """Validate an intake dict. Returns (intake, problems). No filesystem access."""
    problems: List[Dict[str, str]] = []
    allowed = {"name", "project_type", "deploy_model", "brief", "credentials", "code_project"}
    for key in sorted(set(raw) - allowed):
        problems.append({"field": str(key), "problem": "unknown intake field"})
    name = _check_text("name", raw.get("name"), problems, required=True)
    ptype = _check_text("project_type", raw.get("project_type"), problems, required=False)
    if ptype is not None and ptype.lower() not in PROJECT_TYPES:
        problems.append({"field": "project_type", "problem": "must be one of " + ", ".join(PROJECT_TYPES)})
        ptype = None
    deploy = _check_text("deploy_model", raw.get("deploy_model"), problems, required=False)
    if deploy is not None and _no_answer(deploy):
        # Literal UNRESOLVED (also after NFKD, mark stripping or look-alike letters) or a placeholder such as
        # TBD, ?, - or n/a is no answer; it must not finish as complete.
        deploy = None
    brief = _check_text("brief", raw.get("brief"), problems, required=False)
    creds_raw = raw.get("credentials") or []
    creds: List[Dict[str, str]] = []
    if not isinstance(creds_raw, list):
        problems.append({"field": "credentials", "problem": "must be a list"})
        creds_raw = []
    for i, row in enumerate(creds_raw, 1):
        prefix = f"credentials[{i}]"
        if not isinstance(row, dict):
            problems.append({"field": prefix, "problem": "must be an object"})
            continue
        for key in sorted(set(row) - set(CREDENTIAL_KEYS)):
            problems.append({"field": f"{prefix}.{key}", "problem":
                             "unsupported credential field; only system, username and location are recorded"})
        clean = {}
        for key in CREDENTIAL_KEYS:
            val = _check_text(f"{prefix}.{key}", row.get(key), problems, required=key != "username")
            if val is not None and "|" in val:
                problems.append({"field": f"{prefix}.{key}", "problem": "must not contain '|'"})
                val = None
            clean[key] = val or ""
        creds.append(clean)
    code = raw.get("code_project", False)
    if not isinstance(code, bool):
        problems.append({"field": "code_project", "problem": "must be true or false"})
        code = False
    intake = {"name": name, "project_type": ptype.lower() if ptype else None,
              "deploy_model": deploy, "brief": brief, "credentials": creds, "code_project": code}
    return intake, problems


# ---------------------------------------------------------------------------
# Generated documents (deterministic: no timestamps, so repeats are byte-stable)
# ---------------------------------------------------------------------------

HEADER = ("<!-- Generated by project-onboarding activate.py. If you edit this file, later "
          "activations keep your version and report a conflict instead of overwriting it. -->")


def _deploy_line(intake: Dict[str, Any]) -> str:
    if intake["deploy_model"]:
        return f"DEPLOY-MODEL: {intake['deploy_model']}"
    return "DEPLOY-MODEL: UNRESOLVED (no answer recorded; nothing may deploy until the owner states one)"


def render(intake: Dict[str, Any]) -> Dict[str, bytes]:
    name = intake["name"]
    rows = intake["credentials"]
    status = [
        f"# Project status: {name}", "", HEADER, "",
        "## Brief",
        f"- Project name: {name}",
        f"- Project type: {intake['project_type'] or 'not stated'}",
        f"- Brief: {intake['brief'] or 'not recorded'}",
        f"- Code project: {'yes' if intake['code_project'] else 'no'}",
        "- Stage: activated locally (folders and notes only)", "",
        "## Deploy model",
        _deploy_line(intake),
        "- A recorded deploy model is a note of owner intent, not permission to deploy.",
        f"- {EXTERNAL_OWNER_STEPS}", "",
        "## Workspace",
        "- Folders: Scope/, Development/, Delivery/, Assets/",
        f"- Round plan: {PLAN}",
        f"- Credential references: {CREDS} ({len(rows)} row{'s' if len(rows) != 1 else ''}, locations only)",
        "",
    ]
    first = ["Confirm the deploy model with the owner and rerun activation with it."] if not intake["deploy_model"] else []
    plan = [
        f"# Round plan: {name}", "", HEADER, "",
        "## Project brief",
        f"- Name: {name}",
        f"- Type: {intake['project_type'] or 'not stated'}",
        f"- Brief: {intake['brief'] or 'not recorded'}",
        f"- {_deploy_line(intake)}", "",
        "## First work items",
    ] + [f"{i}. {item}" for i, item in enumerate(first + [
        "Review the brief with the owner and write the scope in Scope/.",
        "Record decisions and open questions in Scope/ before building in Development/.",
        "List each human-owned step (accounts, secrets, deployment approval) in STATUS.md.",
    ], 1)] + [""]
    creds = [
        f"# Credential references: {name}", "", HEADER, "",
        "Locations only. Secret values are never written here or in chat.", "",
    ]
    if rows:
        creds += ["| System | Username | Where the secret lives |", "|---|---|---|"]
        creds += [f"| {r['system']} | {r['username'] or '-'} | {r['location']} |" for r in rows]
    else:
        creds.append("No credential references recorded yet.")
    creds.append("")
    return {STATUS: "\n".join(status).encode("utf-8"), PLAN: "\n".join(plan).encode("utf-8"),
            CREDS: "\n".join(creds).encode("utf-8")}


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

def _atomic_write(target: Path, data: bytes) -> None:
    """Write via a fresh exclusive temp file in the same directory, then rename.

    The temp name is random and opened with O_CREAT|O_EXCL (and O_NOFOLLOW where
    available), so a preexisting file or symlink at a predictable temp path is
    never written through. os.replace swaps the directory entry; it does not
    follow a symlink at the target.
    """
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    for _ in range(20):
        tmp = target.parent / f".{target.name}.{secrets.token_hex(8)}.activation-tmp"
        try:
            fd = os.open(tmp, flags, 0o644)
            break
        except FileExistsError:
            continue
    else:
        raise OSError(f"could not create a unique temporary file next to {target.name}")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if _kind(_lstat(target)) not in ("missing", "file"):
            raise OSError(f"{target.name} changed type during activation")
        os.replace(tmp, target)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


TEMP_RE = re.compile(r"^\.(?P<name>.+)\.[0-9a-f]{16}\.activation-tmp$")
TEMP_HOMES = {".": ("STATUS.md", JOURNAL), "Scope": ("ROUND-PLAN.md",), "Delivery": ("CREDENTIALS.md",)}


def _remove_leftover_temps(root: Path) -> List[str]:
    """Delete temp files a killed run left next to its own targets. Called only under the lock.

    Only regular files with this tool's exact temp-name shape for one of its own targets are
    removed; symlinks and anything else are left alone.
    """
    removed = []
    for folder, names in TEMP_HOMES.items():
        d = root if folder == "." else root / folder
        if _kind(_lstat(d)) != "directory":
            continue
        for entry in sorted(os.listdir(d)):
            m = TEMP_RE.match(entry)
            if m and m.group("name") in names and _kind(_lstat(d / entry)) == "file":
                os.unlink(d / entry)
                removed.append(entry if folder == "." else f"{folder}/{entry}")
    return removed


def _read_journal(root: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    path = root / JOURNAL
    kind = _kind(_lstat(path))
    if kind == "missing":
        return None, None
    if kind != "file":
        return None, f"{JOURNAL} is a {kind}, not a regular file; left unchanged"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except RecursionError:
        # Deeply nested JSON escapes the default decoder as an unbounded traceback; refuse bounded.
        return None, (f"{JOURNAL} is too deeply nested or corrupted; left unchanged. "
                      "Move it aside to start a new activation")
    except (OSError, ValueError, UnicodeDecodeError):
        return None, f"{JOURNAL} is unreadable; left unchanged. Move it aside to start a new activation"
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or not isinstance(data.get("files"), dict) \
            or not isinstance(data.get("intake"), dict):
        return None, f"{JOURNAL} has an unknown format; left unchanged. Move it aside to start a new activation"
    for rel, entry in data["files"].items():
        if not isinstance(entry, dict) or any(not isinstance(entry.get(k), (str, type(None))) for k in ("written", "pending")):
            return None, (f"{JOURNAL} has a malformed entry for {str(rel)[:80]!r}; left unchanged. "
                          "Move it aside to start a new activation")
    if not isinstance(data.get("project_root"), (str, type(None))):
        return None, f"{JOURNAL} has a malformed project_root; left unchanged. Move it aside to start a new activation"
    return data, None


# ---------------------------------------------------------------------------
# Git: read-only inspection, optional init of a missing repository
# ---------------------------------------------------------------------------

def _git(root: Path, *args: str, ceiling: bool = True) -> Tuple[int, str]:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0", LC_ALL="C")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR"):
        env.pop(key, None)
    if ceiling:
        env["GIT_CEILING_DIRECTORIES"] = str(root.parent)
    try:
        proc = subprocess.run(["git", "-c", "core.fsmonitor=false", "-C", str(root), *args],
                              capture_output=True, text=True, env=env, timeout=30)
    except FileNotFoundError:
        return 127, "git not found"
    except subprocess.TimeoutExpired:
        return 124, "git timed out"
    return proc.returncode, (proc.stdout.strip() or proc.stderr.strip())


def _inspect_git(root: Path) -> Dict[str, Any]:
    dot = root / ".git"
    kind = _kind(_lstat(dot))
    if kind == "missing":
        return {"state": "absent"}
    if kind in ("symlink", "other"):
        return {"state": "not_inspected", "reason": f".git is a {kind}; activation does not use repository "
                "metadata reached through it"}
    rc, top = _git(root, "rev-parse", "--show-toplevel")
    if rc != 0:
        return {"state": "invalid", "reason": f"existing .git is not a usable repository (git exit {rc}); left unchanged"}
    if Path(top).resolve() != root:
        return {"state": "invalid", "reason": "repository top level is not the project root; left unchanged"}
    rc, gitdir = _git(root, "rev-parse", "--absolute-git-dir")
    info: Dict[str, Any] = {"state": "existing"}
    if rc == 0 and Path(gitdir).resolve() != (root / ".git").resolve():
        info["linked_metadata"] = True  # worktree or submodule gitfile; still read-only here
    rc, ref = _git(root, "symbolic-ref", "-q", "HEAD")
    info["branch"] = ref.replace("refs/heads/", "", 1) if rc == 0 else None
    rc, head = _git(root, "rev-parse", "-q", "--verify", "HEAD")
    info["head"] = head if rc == 0 else None
    info["unborn"] = rc != 0
    return info


def _git_step(root: Path, code_project: bool, init_git: bool, dry_run: bool) -> Tuple[Dict[str, Any], List[str], List[str]]:
    """Return (git_info, gaps, errors). Never modifies an existing repository."""
    gaps: List[str] = []
    errors: List[str] = []
    if not code_project:
        return {"state": "skipped", "reason": "not a code project"}, gaps, errors
    info = _inspect_git(root)
    state = info["state"]
    if state == "existing":
        info["modified"] = False
        if info["unborn"]:
            gaps.append("Repository has no commit yet; the first commit is an owner step (staged files were not touched).")
        gaps.append("Integration branch and CI are not created by activation; the owner decides them.")
        return info, gaps, errors
    if state in ("invalid", "not_inspected"):
        gaps.append(f"Git: {info['reason']}.")
        return info, gaps, errors
    # absent
    if not init_git:
        gaps.append("No Git repository. Rerun with --init-git to create an empty one, or create it yourself.")
        return info, gaps, errors
    rc, outer = _git(root, "rev-parse", "--show-toplevel", ceiling=False)
    if rc == 0:
        info.update(state="inside_other_repository",
                    reason="project root is inside another repository; nested init not performed")
        gaps.append("Git: project root is inside another repository; activation did not create a nested one.")
        return info, gaps, errors
    if dry_run:
        info.update(state="would_init")
        return info, gaps, errors
    rc, out = _git(root, "init", "-q", "--initial-branch=main")
    if rc != 0:
        errors.append(f"git init failed (exit {rc}); no repository created")
        info.update(state="init_failed")
        return info, gaps, errors
    after = _inspect_git(root)
    if after.get("state") != "existing":
        errors.append("git init reported success but the repository could not be verified")
        info.update(state="init_unverified")
        return info, gaps, errors
    after.update(state="initialized_unborn", modified=True)
    gaps.append("New empty repository on 'main' with no commit; first commit, integration branch and CI are owner steps.")
    return after, gaps, errors


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------

def _result(status: str, root: Optional[Path], **extra: Any) -> Dict[str, Any]:
    exit_code = {"complete": 0, "partial": 0, "dry_run": 0, "blocked": 1, "failed": 1, "invalid": 2}[status]
    res = {"schema": SCHEMA, "status": status, "ok": exit_code == 0, "exit_code": exit_code,
           "project_root": str(root) if root else None, "changed": [], "artifacts": {}, "folders": {},
           "intake": None, "intake_changes": [], "inherited": [], "git": None, "gaps": [], "errors": [],
           "problems": []}
    res.update(extra)
    return res


def _acquire_lock(root: Path) -> Optional[str]:
    """Create the per-project lock exclusively. Returns an error text when it is held."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(root / LOCK, flags, 0o644)
    except FileExistsError:
        holder = "unknown holder"
        st = _lstat(root / LOCK)
        if _kind(st) != "file":
            return f"{LOCK} exists but is not a regular file; it was left unchanged and nothing was written."
        if st is not None and st.st_size == 0:
            holder = ("empty lock: the run that created it was most likely killed before recording itself "
                      "(stale lock)")
        else:
            try:
                info = json.loads((root / LOCK).read_text(encoding="utf-8"))
            except RecursionError:
                return (f"{LOCK} is too deeply nested or corrupted; left unchanged and nothing was written. "
                        f"If no activation is running, delete {LOCK} and rerun.")
            except (OSError, ValueError, UnicodeDecodeError):
                info = None
            if isinstance(info, dict):
                holder = f"pid {info.get('pid')} on {info.get('host')} since {info.get('started')}"
                if info.get("host") == socket.gethostname() and isinstance(info.get("pid"), int) and info["pid"] > 0:
                    try:
                        os.kill(info["pid"], 0)
                    except ProcessLookupError:
                        holder += ", which is no longer running (stale lock)"
                    except (PermissionError, OverflowError):
                        pass
        return (f"another activation holds {LOCK} ({holder}); nothing written. If no activation is "
                f"running, delete {LOCK} and rerun.")
    except OSError as exc:  # read-only root, quota, ...: os.open raised before anything was created
        return f"could not create {LOCK}: {exc.strerror or exc}; nothing written. Fix the cause and rerun."
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"pid": os.getpid(), "host": socket.gethostname(), "started": _now()}, fh)
    return None


def activate(root_arg: str, intake_raw: Optional[Dict[str, Any]] = None, *, resume: bool = False,
             within: Optional[str] = None, init_git: bool = False, dry_run: bool = False,
             _before_write: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """Activate or resume a project root. Returns a result dict; never raises for expected failures.

    A write run first validates and preflights without writing, then creates the root
    if needed, takes an exclusive per-project lock and repeats the whole check under
    it, so concurrent runs on one project cannot interleave writes.
    """
    kwargs = dict(resume=resume, within=within, init_git=init_git)
    pre = _activate(root_arg, intake_raw, dry_run=True, **kwargs)
    if dry_run or pre["status"] in ("invalid", "blocked"):
        return pre
    root = Path(pre["project_root"])
    created_root = False
    try:
        os.mkdir(root)
        created_root = True
    except FileExistsError:
        pass  # created meanwhile by someone else; the locked recheck below decides
    except OSError as exc:
        return _result("failed", root, errors=[f"could not create the project root: {exc.strerror or exc}"])
    if _kind(_lstat(root)) != "directory" and not root.is_dir():
        return _result("blocked", root, errors=["project root changed type during activation; nothing written"])
    held = _acquire_lock(root)
    if held:
        return _result("blocked", root, errors=[held], intake=pre.get("intake"))
    try:
        res = _activate(root_arg, intake_raw, dry_run=False, _before_write=_before_write, **kwargs)
    finally:
        try:
            os.unlink(root / LOCK)
        except OSError:
            pass
    if created_root and "." not in res["changed"]:
        res["changed"].insert(0, ".")
    return res


def _activate(root_arg: str, intake_raw: Optional[Dict[str, Any]] = None, *, resume: bool = False,
              within: Optional[str] = None, init_git: bool = False, dry_run: bool = False,
              _before_write: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
    """One activation pass (see activate).

    intake_raw fields: name, project_type, deploy_model, brief, credentials (list of
    {system, username, location}), code_project. Omitted fields on a rerun inherit
    the journal's values. With resume=True the journal intake is used unchanged.
    _before_write(relpath) is a test hook called before each generated write.
    """
    supplied = dict(intake_raw or {})
    # -- root and boundary --------------------------------------------------------
    root_path = Path(root_arg).expanduser()
    if not root_path.is_absolute():
        root_path = Path.cwd() / root_path
    too_long = _path_problem(root_path)
    if too_long:
        return _result("invalid", root_path, problems=[{"field": "project_root", "problem": too_long}])
    if within is not None:
        boundary = Path(within).expanduser().resolve()
        try:
            root_path.resolve().relative_to(boundary)
            inside = root_path.resolve() != boundary
        except ValueError:
            inside = False
        if not inside:
            return _result("invalid", root_path, problems=[{"field": "project_root", "problem":
                           "resolves outside the --within boundary (or equals it)"}])
    root_kind = _kind(_lstat(root_path))
    if root_kind == "symlink" and root_path.resolve().is_dir():
        root_kind = "directory"  # an explicitly named symlinked root is allowed; its target is reported
    if root_kind not in ("missing", "directory"):
        return _result("blocked", root_path, errors=[f"project root is a {root_kind}, not a directory; nothing written"])
    if root_kind == "missing" and not root_path.parent.is_dir():
        return _result("blocked", root_path, errors=["parent of the project root does not exist; nothing written"])
    root = root_path.resolve() if root_kind == "directory" else root_path.parent.resolve() / root_path.name

    # -- journal and intake ------------------------------------------------------------
    journal, jerr = (None, None) if root_kind == "missing" else _read_journal(root)
    if jerr:
        return _result("blocked", root, errors=[jerr])
    if resume:
        if journal is None:
            return _result("invalid", root, problems=[{"field": "resume", "problem":
                           "no activation journal in this project root; run activate first"}])
        supplied = dict(journal["intake"])
    # The journal is bound to the folder it was written in. A journal copied with a project
    # folder (or on its own) belongs to another project: nothing is inherited from it.
    foreign_gap = None
    if journal is not None and journal.get("project_root") != str(root):
        origin = journal.get("project_root")
        head = (f"{JOURNAL} was written for another folder ({origin})" if origin else
                f"{JOURNAL} does not record which folder it belongs to")
        if resume:
            return _result("blocked", root, errors=[head + "; resume refused, nothing written. "
                           "Run activate with this project's intake, or move the journal aside."])
        foreign_gap = head + ("; nothing was inherited from it (deploy model, brief, credentials). "
                              "State them again if they apply here.")
    previous = journal["intake"] if journal and not foreign_gap else {}
    inherited = []
    for key in ("name", "project_type", "deploy_model", "brief", "credentials", "code_project"):
        if key not in supplied and key in previous:
            supplied[key] = previous[key]
            inherited.append(key)
    intake, problems = normalize_intake(supplied)
    if problems:
        return _result("invalid", root, problems=problems)
    changes = [{"field": k, "previous": previous.get(k), "current": intake[k]}
               for k in intake if previous and previous.get(k) != intake[k]]
    desired = render(intake)

    # -- preflight: every controlled path, before any write ---------------------------------
    blocked: List[str] = []
    folders: Dict[str, str] = {}
    for name in FOLDERS:
        k = "missing" if root_kind == "missing" else _kind(_lstat(root / name))
        if k == "missing":
            folders[name] = "create"
        elif k == "directory":
            folders[name] = "existing"
        else:
            blocked.append(f"{name}/ is a {k}; expected a real directory inside the project. It was left unchanged")
    for rel in GENERATED:
        k = "missing" if root_kind == "missing" else _kind(_lstat(root / rel))
        if k not in ("missing", "file"):
            blocked.append(f"{rel} is a {k}; expected a regular file. It was left unchanged")
    if blocked:
        return _result("blocked", root, errors=blocked, intake=intake)

    # -- classify generated files against the journal -----------------------------------
    jfiles = journal["files"] if journal else {}
    artifacts: Dict[str, str] = {}
    current_hash: Dict[str, Optional[str]] = {}
    for rel in GENERATED:
        path = root / rel
        cur = None if root_kind == "missing" or _kind(_lstat(path)) == "missing" else _sha(path.read_bytes())
        current_hash[rel] = cur
        entry = jfiles.get(rel) or {}
        known = {entry.get("written"), entry.get("pending")} - {None}
        if cur is None:
            artifacts[rel] = "create"
        elif cur == _sha(desired[rel]):
            artifacts[rel] = "unchanged"
        elif cur in known:
            artifacts[rel] = "update"
        else:
            artifacts[rel] = "conflict_preserved"

    gaps: List[str] = [foreign_gap] if foreign_gap else []
    if not intake["deploy_model"]:
        gaps.append("Deploy model unresolved: recorded as UNRESOLVED; nothing may deploy until the owner states one.")
    if not intake["project_type"]:
        gaps.append("Project type not stated.")
    for rel, action in artifacts.items():
        if action == "conflict_preserved":
            gaps.append(f"{rel} exists with content activation did not write; it was kept unchanged and the "
                        "generated version was not applied. Merge it by hand or move it aside and rerun.")

    if dry_run:
        git_info, ggaps, gerrs = _git_step(root, intake["code_project"], init_git, dry_run=True) \
            if root_kind != "missing" else ({"state": "absent"}, [], [])
        return _result("dry_run", root, intake=intake, intake_changes=changes, inherited=inherited,
                       folders=folders, artifacts=artifacts, git=git_info, gaps=gaps + ggaps + [EXTERNAL_OWNER_STEPS])

    # -- writes: journal first (intent), then folders and files, journal after each --------
    to_write = [rel for rel, a in artifacts.items() if a in ("create", "update")]
    needs_dirs = [n for n, a in folders.items() if a == "create"]
    changed: List[str] = []
    errors: List[str] = []
    removed: List[str] = []
    new_files = {rel: dict(jfiles.get(rel) or {}) for rel in GENERATED}
    for rel in GENERATED:
        if artifacts[rel] in ("unchanged", "update"):
            new_files[rel]["written"] = current_hash[rel]  # current content is tool output
        if artifacts[rel] != "conflict_preserved":
            new_files[rel]["pending"] = _sha(desired[rel])
    jstate = {"schema": SCHEMA, "state": "in_progress", "intake": intake, "files": new_files, "project_root": str(root),
              "created_at": (journal or {}).get("created_at") or _now(), "updated_at": _now(),
              "git_initialized_by_activation": bool((journal or {}).get("git_initialized_by_activation"))}

    def save_journal() -> None:
        _atomic_write(root / JOURNAL, (json.dumps(jstate, indent=2, sort_keys=True) + "\n").encode("utf-8"))

    something_to_do = bool(to_write or needs_dirs or changes or journal is None or foreign_gap
                           or (journal or {}).get("state") != "done")
    current: Optional[str] = None
    try:
        if root_kind == "missing":
            os.mkdir(root)
            changed.append(".")
        removed = _remove_leftover_temps(root) if root_kind != "missing" else []
        if something_to_do:
            current = JOURNAL
            save_journal()
            current = None
        for name in needs_dirs:
            os.mkdir(root / name)  # raises if something appeared there meanwhile
            folders[name] = "created"
            changed.append(name + "/")
        for rel in to_write:
            current = rel
            if _before_write:
                _before_write(rel)
            _atomic_write(root / rel, desired[rel])
            artifacts[rel] = "created" if artifacts[rel] == "create" else "updated"
            new_files[rel]["written"] = _sha(desired[rel])
            changed.append(rel)
            current = JOURNAL
            save_journal()
    except OSError as exc:
        where = current or (Path(exc.filename).name if getattr(exc, "filename", None) else "unknown path")
        errors.append(f"write failed at {where}: {exc.strerror or exc}; files already written were kept and the "
                      "journal records progress. Fix the cause and run resume.")
        return _result("failed", root, intake=intake, intake_changes=changes, inherited=inherited,
                       folders=folders, artifacts=artifacts, changed=changed, errors=errors,
                       removed_temp_files=removed, gaps=gaps + [EXTERNAL_OWNER_STEPS])

    git_info, ggaps, gerrs = _git_step(root, intake["code_project"], init_git, dry_run=False)
    if git_info.get("state") == "initialized_unborn":
        jstate["git_initialized_by_activation"] = True
        changed.append(".git/")
    gaps += ggaps
    errors += gerrs
    status = "failed" if errors else ("partial" if gaps else "complete")
    if something_to_do or git_info.get("state") == "initialized_unborn":
        jstate["state"] = "done"
        jstate["last_status"] = status
        try:
            save_journal()
        except OSError as exc:
            errors.append(f"could not finalize {JOURNAL}: {exc.strerror or exc}; run resume")
            status = "failed"
    return _result(status, root, intake=intake, intake_changes=changes, inherited=inherited,
                   folders=folders, artifacts=artifacts, changed=changed, git=git_info,
                   removed_temp_files=removed, gaps=gaps + [EXTERNAL_OWNER_STEPS], errors=errors)


def report_lines(res: Dict[str, Any]) -> List[str]:
    """The skill's 5-line report."""
    intake = res.get("intake") or {}
    rows = len(intake.get("credentials") or [])
    git = res.get("git") or {}
    human = [g for g in res.get("gaps", []) if g != EXTERNAL_OWNER_STEPS]
    return [
        f"Folder: {res.get('project_root')} ({res['status']})",
        f"Deploy model: {intake.get('deploy_model') or 'UNRESOLVED'}"
        + (" (carried over from this folder's earlier activation, not restated)"
           if intake.get("deploy_model") and "deploy_model" in res.get("inherited", []) else ""),
        f"Credential reference rows: {rows} (locations only)",
        f"Repo: {git.get('state', 'not checked')}" + (f", branch {git['branch']}" if git.get("branch") else ""),
        "Needs a human: " + ("fix the invalid input listed below; nothing was written" if res["status"] == "invalid"
                             else "; ".join(human + res.get("errors", [])) or "nothing beyond owner-approved external steps"),
    ]


def _parse_credential(text: str) -> Dict[str, str]:
    row: Dict[str, str] = {}
    for part in text.split(";"):
        if not part.strip():
            continue
        key, sep, value = part.partition("=")
        row[key.strip()] = value.strip() if sep else ""
    return row


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Conservative local project activation and resume.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    act = sub.add_parser("activate", help="Create or update local project folders and notes")
    act.add_argument("project_root")
    act.add_argument("--name")
    act.add_argument("--type", dest="project_type", help="one of: " + ", ".join(PROJECT_TYPES))
    act.add_argument("--deploy-model", help="owner's deploy answer; omit or leave blank if not given")
    act.add_argument("--brief", help="one-line project brief")
    act.add_argument("--credential", action="append", metavar="system=..;username=..;location=..",
                     help="credential reference (location of the secret, never the secret); repeatable")
    act.add_argument("--code", action="store_true", default=None, help="this is a code project (inspect Git)")
    act.add_argument("--init-git", action="store_true", help="for a code project with no repository, run git init")
    act.add_argument("--within", help="refuse unless the project root resolves inside this directory")
    act.add_argument("--dry-run", action="store_true", help="report what would change; write nothing")
    res_p = sub.add_parser("resume", help="Rerun the journal's intake (after an interruption)")
    res_p.add_argument("project_root")
    res_p.add_argument("--init-git", action="store_true")
    res_p.add_argument("--within")
    res_p.add_argument("--dry-run", action="store_true")
    for p in (act, res_p):
        p.add_argument("--json", action="store_true", help="print the full JSON result")
    args = parser.parse_args(argv)
    if args.cmd == "activate":
        raw: Dict[str, Any] = {}
        for key in ("name", "project_type", "deploy_model", "brief"):
            if getattr(args, key) is not None:
                raw[key] = getattr(args, key)
        if args.credential is not None:
            raw["credentials"] = [_parse_credential(c) for c in args.credential]
        if args.code:
            raw["code_project"] = True
        res = activate(args.project_root, raw, within=args.within, init_git=args.init_git, dry_run=args.dry_run)
    else:
        res = activate(args.project_root, resume=True, within=args.within, init_git=args.init_git,
                       dry_run=args.dry_run)
    if args.json:
        print(json.dumps(res, indent=2, sort_keys=True))
    else:
        for line in report_lines(res):
            print(line)
        for p in res.get("problems", []):
            print(f"  invalid {p['field']}: {p['problem']}")
    return res["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
