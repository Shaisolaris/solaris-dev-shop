#!/usr/bin/env python3
"""M02 activation oracle (written for M02; independent of the builder's activation_oracle.py and tests).

Derived from the G02/M02 acceptance text:
  disposable activation works twice; outside sentinels and owner Git index unchanged;
  failure between writes resumes consistently; no silent live authority; owner
  documents preserved; changed intake during interruption reported truthfully;
  symlink and path escape refused.

Black-box interface, taken from project-onboarding/SKILL.md only:
  <cmd> activate ROOT --name N [--type T] [--deploy-model D] [--credential S] [--code] [--init-git]
                      [--within DIR] [--json]
  <cmd> resume ROOT [--json]
--json prints a result object with a "status" field (complete/partial/blocked/failed/invalid).
Every check asserts filesystem, Git or status outcomes. A candidate that writes nothing,
echoes its input, crashes or prints non-JSON cannot pass. No check can SKIP into a pass.

Usage: python m02_oracle.py [--only K1,K2] -- <candidate command prefix...>
Synthetic data and disposable temp directories only. Python standard library only.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
INJECT = HERE / "inject"
DOCS = ("STATUS.md", "Scope/ROUND-PLAN.md", "Delivery/CREDENTIALS.md")
FOLDERS = ("Scope", "Development", "Delivery", "Assets")
LOCKNAME = ".solaris-activation.lock"
FAKE_TOKEN = "ghp_" + "Zx9" * 12  # synthetic token-shaped string, not a credential
GITX = ["git", "-c", "user.name=M02 Oracle", "-c", "user.email=m02@example.invalid",
        "-c", "core.hooksPath=/dev/null", "-c", "init.defaultBranch=main", "-c", "commit.gpgsign=false"]
CMD = []


class Fail(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Fail(msg)


def clean_env(extra=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra or {})
    return env


def run(*args, env=None, timeout=120):
    try:
        p = subprocess.run(CMD + [str(a) for a in args], capture_output=True, text=True,
                           env=clean_env(env), timeout=timeout)
    except subprocess.TimeoutExpired:
        raise Fail(f"candidate timed out: {args[:2]}")
    return p.returncode, p.stdout, p.stderr


def status_of(out):
    try:
        data = json.loads(out)
    except ValueError:
        return None
    return data.get("status") if isinstance(data, dict) else None


def jrun(*args, env=None):
    rc, out, err = run(*args, "--json", env=env)
    return rc, status_of(out), out + err


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def snap(base, exclude=None):
    """Hash every entry under base (links by target, never followed); exclude one subtree."""
    base = Path(base)
    out = {}
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        for n in dirnames + filenames:
            p = Path(dirpath) / n
            rel = p.relative_to(base).as_posix()
            if exclude and (rel == exclude or rel.startswith(exclude + "/")):
                continue
            if p.is_symlink():
                out[rel] = "link:" + os.readlink(p)
            elif p.is_file():
                out[rel] = sha(p) + ":" + oct(p.stat().st_mode & 0o777)
            else:
                out[rel] = "dir"
    return out


def text(root, rel):
    return (Path(root) / rel).read_text(encoding="utf-8")


def deploy_lines(root):
    return [l for l in text(root, "STATUS.md").splitlines() if l.startswith("DEPLOY-MODEL:")]


def git(cwd, *args, check=True):
    p = subprocess.run(GITX + ["-C", str(cwd), *args], capture_output=True, text=True, env=clean_env())
    if check and p.returncode != 0:
        raise RuntimeError(f"oracle git setup failed: {args}: {p.stderr}")
    return p.stdout.strip()


def git_state(repo):
    """Refs, HEAD, index bytes, all reachable history, stash, config: anything activation must not change."""
    gitdir = Path(git(repo, "rev-parse", "--absolute-git-dir"))
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    idx = gitdir / "index"
    return {
        "refs": git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
        "head_sym": git(repo, "symbolic-ref", "-q", "HEAD", check=False),
        "head": git(repo, "rev-parse", "-q", "--verify", "HEAD", check=False),
        "index": sha(idx) if idx.exists() else None,
        "log": git(repo, "log", "--all", "--format=%H %P", check=False),
        "objects": git(repo, "count-objects", "-v"),
        "config": sha(common / "config"),
        "cached": git(repo, "diff", "--cached", "--name-status", check=False),
    }


def assert_docs(root, name, deploy=None):
    for f in FOLDERS:
        p = Path(root) / f
        need(p.is_dir() and not p.is_symlink(), f"{f}/ is not a real directory")
    for d in DOCS:
        p = Path(root) / d
        need(p.is_file() and not p.is_symlink(), f"{d} missing or not a regular file")
        need(name in text(root, d), f"{d} does not name the project {name!r}")
    lines = deploy_lines(root)
    need(len(lines) == 1, f"STATUS.md must carry exactly one DEPLOY-MODEL line, found {lines}")
    if deploy is None:
        need(re.match(r"DEPLOY-MODEL:\s*UNRESOLVED\b", lines[0]), f"deploy not UNRESOLVED: {lines[0]!r}")
    else:
        need(lines[0].strip() == f"DEPLOY-MODEL: {deploy}", f"deploy not recorded verbatim: {lines[0]!r}")


def leftovers(root):
    known = set(DOCS) | {".solaris-activation.json"} | set(FOLDERS)
    return sorted(r for r in snap(root, exclude=".git") if r not in known)


def fresh(tmp, label):
    base = Path(tempfile.mkdtemp(prefix=label + "-", dir=tmp)).resolve()
    out = base / "outside"
    out.mkdir()
    (out / "sentinel.txt").write_text("OUTSIDE SENTINEL - must never change\n")
    (out / "CREDENTIALS.md").write_text("outside credential notes - must never change\n")
    return base, base / "proj"


# ----------------------------------------------------------------------------- checks

def k1_clean_twice(tmp):
    base, root = fresh(tmp, "k1")
    args = ["activate", root, "--name", "Orchard Ledger", "--type", "web app",
            "--deploy-model", "staging only, owner approves prod", "--brief", "Inventory tool",
            "--credential", "system=github;username=orchard-bot;location=Vault/eng/github"]
    rc, st, log = jrun(*args)
    need(rc == 0 and st in ("complete", "partial"), f"first run rc={rc} status={st}")
    assert_docs(root, "Orchard Ledger", "staging only, owner approves prod")
    need("Vault/eng/github" in text(root, DOCS[2]), "credential location row missing")
    s1 = snap(root)
    rc, st2, _ = jrun(*args)
    need(rc == 0 and snap(root) == s1, "second identical activation changed the tree")
    rc, st3, _ = jrun("resume", root)
    need(rc == 0 and snap(root) == s1, "resume after a complete run changed the tree")
    need(st == st2 == st3, f"statuses differ across identical runs: {st},{st2},{st3}")
    need(not leftovers(root), f"unexpected files: {leftovers(root)}")
    return f"two activations + resume byte-identical ({len(s1)} entries), status {st}"


def k2_owner_docs(tmp):
    base, root = fresh(tmp, "k2")
    root.mkdir()
    owner = {"STATUS.md": "# My own status\nDEPLOY-MODEL: owner wrote this\n", "README.md": "owner readme\n",
             "Scope/notes.md": "owner scope notes\n", "Development/app.py": "print('owner code')\n",
             "Assets/logo.txt": "owner asset\n"}
    for rel, body in owner.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(body)
    before = {rel: sha(root / rel) for rel in owner}
    rc, st, log = jrun("activate", root, "--name", "Keeper", "--type", "website", "--deploy-model", "none")
    need(rc == 0, f"rc={rc}")
    for rel in owner:
        need(sha(root / rel) == before[rel], f"owner file changed: {rel}")
    need((root / DOCS[1]).is_file() and (root / DOCS[2]).is_file(), "missing generated docs not created")
    need(st != "complete", f"owner STATUS.md was kept but run claims complete (status {st})")
    need("conflict" in log.lower(), "kept owner STATUS.md not reported as a conflict")
    rc, st2, _ = jrun("activate", root, "--name", "Keeper", "--type", "website", "--deploy-model", "none")
    need(all(sha(root / r) == before[r] for r in owner), "owner file changed on rerun")
    return f"5 owner files byte-identical across 2 runs; conflict reported; status {st}"


def _history_repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    (path / "app.txt").write_text("v1\n")
    git(path, "add", "app.txt"); git(path, "commit", "-qm", "one")
    (path / "app.txt").write_text("v2\n")
    git(path, "commit", "-qam", "two")
    git(path, "branch", "feature-x")
    (path / "staged.txt").write_text("staged by owner\n"); git(path, "add", "staged.txt")
    (path / "app.txt").write_text("v3 unstaged\n")
    (path / "untracked.txt").write_text("untracked\n")


def k3_git_and_outside(tmp):
    base, root = fresh(tmp, "k3")
    _history_repo(root)
    (base / "sibling").mkdir(); (base / "sibling" / "keep.txt").write_text("sibling\n")
    outside_before = snap(base, exclude="proj")
    g0 = git_state(root)
    owned = {r: sha(root / r) for r in ("app.txt", "staged.txt", "untracked.txt")}
    rc, st, log = jrun("activate", root, "--name", "Repo Keeper", "--type", "web app", "--code",
                       "--deploy-model", "manual")
    need(rc == 0, f"rc={rc}: {log[-300:]}")
    assert_docs(root, "Repo Keeper", "manual")
    need(git_state(root) == g0, "owner Git refs/HEAD/index/history/config changed")
    need(all(sha(root / r) == h for r, h in owned.items()), "owner working files changed")
    need(snap(base, exclude="proj") == outside_before, "outside sentinel tree changed")
    rc, st, log = jrun("activate", root, "--name", "Repo Keeper", "--type", "web app", "--code",
                       "--init-git", "--deploy-model", "manual")
    need(git_state(root) == g0, "--init-git on an existing repo changed Git state")
    return "2 commits, branch, staged + unstaged + untracked: Git state and outside tree identical"


def k4_unborn_and_worktree(tmp):
    base, root = fresh(tmp, "k4")
    root.mkdir(); git(root, "init", "-q")
    (root / "draft.txt").write_text("private draft staged by owner\n"); git(root, "add", "draft.txt")
    g0 = git_state(root)
    rc, st, log = jrun("activate", root, "--name", "Unborn", "--code", "--init-git", "--deploy-model", "none")
    need(rc == 0, f"unborn rc={rc}")
    need(git_state(root) == g0, "unborn repo: index/refs/objects changed (commit or stage happened)")
    need(st != "complete", "unborn repo with no commit reported complete")
    main = base / "mainrepo"
    _history_repo(main)
    git(main, "worktree", "add", "-q", str(base / "wt"), "-b", "wt-branch")
    wt = base / "wt"
    gm, gw = git_state(main), git_state(wt)
    outside_before = snap(base, exclude="wt")
    rc, st, log = jrun("activate", wt, "--name", "Worktree Proj", "--code", "--deploy-model", "none")
    need(rc == 0, f"worktree rc={rc}: {log[-300:]}")
    assert_docs(wt, "Worktree Proj", "none")
    need(git_state(main) == gm and git_state(wt) == gw, "linked worktree: owner Git state changed")
    after = snap(base, exclude="wt")
    need({k: v for k, v in after.items() if not k.startswith("mainrepo/.git/")} ==
         {k: v for k, v in outside_before.items() if not k.startswith("mainrepo/.git/")},
         "main checkout files changed")
    return "unborn staged repo and linked worktree: refs/HEAD/index/objects identical, no commit"


def _setup_alpha(tmp, label):
    base, root = fresh(tmp, label)
    rc, st, _ = jrun("activate", root, "--name", "Alpha", "--type", "web app", "--deploy-model", "staging-alpha")
    need(rc == 0, f"setup Alpha rc={rc}")
    assert_docs(root, "Alpha", "staging-alpha")
    return base, root


def k5_interrupt_resume(tmp):
    base, root = fresh(tmp, "k5")
    root.mkdir(); (root / "Scope").mkdir()
    os.chmod(root / "Scope", 0o555)  # real EACCES on the Scope write
    try:
        rc, st, log = jrun("activate", root, "--name", "Halted", "--type", "game", "--deploy-model", "itch.io manual")
    finally:
        os.chmod(root / "Scope", 0o755)
    need(rc != 0, f"a run that could not write Scope/ROUND-PLAN.md exited 0 (status {st})")
    need(st not in ("complete", "partial"), f"failed write reported as {st}")
    need(not (root / DOCS[1]).exists(), "plan exists although its write was denied")
    rc, st, log = jrun("resume", root)
    if rc != 0 and "resume" in log.lower() and not (root / ".solaris-activation.json").exists():
        rc, st, log = jrun("activate", root, "--name", "Halted", "--type", "game", "--deploy-model", "itch.io manual")
    need(rc == 0, f"resume after fixing the cause failed rc={rc}: {log[-300:]}")
    assert_docs(root, "Halted", "itch.io manual")
    s = snap(root)
    rc, _, _ = jrun("resume", root)
    need(rc == 0 and snap(root) == s, "second resume not stable")
    need(not leftovers(root), f"leftover files: {leftovers(root)}")
    return "EACCES between writes -> non-zero, plan absent; resume completes; stable; no leftovers"


def k6_sigkill_resume(tmp):
    detail = []
    killed = 0
    for n in range(1, 13):
        base, root = fresh(tmp, f"k6-{n}")
        args = ["activate", root, "--name", "Killed", "--type", "website", "--deploy-model", "netlify by owner"]
        rc, out, err = run(*args, env={"M02_KILL_ROOT": str(base), "M02_KILL_AT": str(n),
                                       "PYTHONPATH": str(INJECT)})
        if rc == -9:
            killed += 1
        # documented recovery (SKILL.md): a killed run leaves a lock the tool reports as stale and
        # the owner deletes; then resume, or rerun activate when no journal was recorded yet.
        rc, st, log = 1, None, ""
        for _ in range(3):
            if (root / LOCKNAME).exists():
                rc, st, log = jrun("resume", root) if (root / ".solaris-activation.json").exists() else jrun(*args)
                need("stale" in log.lower(), f"kill@{n}: leftover lock not reported as stale: {log[-200:]}")
                os.unlink(root / LOCKNAME)
            rc, st, log = jrun("resume", root) if (root / ".solaris-activation.json").exists() else jrun(*args)
            if rc == 0:
                break
        need(rc == 0, f"kill@{n}: recovery failed rc={rc}: {log[-300:]}")
        assert_docs(root, "Killed", "netlify by owner")
        need(st == "complete", f"kill@{n}: no owner edits, yet recovery ends {st}: the tool lost track of its own writes")
        need(not (root / LOCKNAME).exists(), f"kill@{n}: lock left after recovery")
        s = snap(root)
        rc, _, _ = jrun("resume", root)
        need(rc == 0 and snap(root) == s, f"kill@{n}: resume after recovery not stable")
        extra = [r for r in leftovers(root) if r != LOCKNAME]
        if extra:
            detail.append(f"kill@{n} leftover {extra}")
    need(killed >= 3, f"fault injection only killed {killed} runs: candidate wrote too little to interrupt")
    # changed intake killed mid-write, then the owner reruns with yet another intake: the tool must
    # recognise its own partial writes (not invent owner conflicts) and converge on the last intake.
    for n in range(1, 13):
        base, root = _setup_alpha(tmp, f"k6c-{n}")
        rc, _, _ = run("activate", root, "--name", "Beta", "--deploy-model", "prod-beta",
                       env={"M02_KILL_ROOT": str(base), "M02_KILL_AT": str(n), "PYTHONPATH": str(INJECT)})
        gamma = ["activate", root, "--name", "Gamma", "--type", "web app", "--deploy-model", "prod-gamma"]
        if (root / LOCKNAME).exists():
            rc, st, log = jrun(*gamma)
            need("stale" in log.lower(), f"changed kill@{n}: lock not reported stale")
            os.unlink(root / LOCKNAME)
        rc, st, log = jrun(*gamma)
        need(rc == 0, f"changed kill@{n}: Gamma rerun rc={rc}")
        need(all("Gamma" in text(root, d) and "Beta" not in text(root, d) and "Alpha" not in text(root, d) for d in DOCS),
             f"changed kill@{n}: docs did not converge on Gamma")
        need(st == "complete", f"changed kill@{n}: Gamma rerun ends {st}: own partial write mistaken for owner content")
    return f"{killed} SIGKILLs at write events 1..12, all recovered consistently" + \
           (f"; WARN temp leftovers: {'; '.join(detail)}" if detail else "")


def k7_changed_intake_interruption(tmp):
    # A: Alpha complete -> Beta interrupted between writes -> Gamma rerun converges
    base, root = _setup_alpha(tmp, "k7a")
    os.chmod(root / "Scope", 0o555)
    try:
        rc, st, _ = jrun("activate", root, "--name", "Beta", "--deploy-model", "prod-beta")
    finally:
        os.chmod(root / "Scope", 0o755)
    need(rc != 0 and st not in ("complete", "partial"), f"interrupted Beta reported rc={rc} status={st}")
    mixed = "Beta" in text(root, "STATUS.md") and "Alpha" in text(root, DOCS[1])
    rc, st, log = jrun("activate", root, "--name", "Gamma", "--deploy-model", "prod-gamma")
    need(rc == 0, f"Gamma rc={rc}")
    for d in DOCS:
        t = text(root, d)
        need("Gamma" in t and "Alpha" not in t and "Beta" not in t, f"{d} not converged on Gamma")
    assert_docs(root, "Gamma", "prod-gamma")
    need("prod-alpha" not in text(root, DOCS[1]) and "staging-alpha" not in text(root, DOCS[1]), "plan kept old deploy")
    # B: interrupted Beta, then plain resume converges on Beta everywhere
    base, root = _setup_alpha(tmp, "k7b")
    os.chmod(root / "Delivery", 0o555)
    try:
        rc, st, _ = jrun("activate", root, "--name", "Beta", "--deploy-model", "prod-beta")
    finally:
        os.chmod(root / "Delivery", 0o755)
    need(rc != 0, "interrupted Beta (Delivery) exited 0")
    rc, st, _ = jrun("resume", root)
    need(rc == 0, f"resume rc={rc}")
    assert_docs(root, "Beta", "prod-beta")
    need(all("Alpha" not in text(root, d) for d in DOCS), "resume left Alpha in a doc")
    # C: owner hand-edits the stale plan during the interruption: kept, and not reported complete
    base, root = _setup_alpha(tmp, "k7c")
    os.chmod(root / "Scope", 0o555)
    try:
        jrun("activate", root, "--name", "Beta", "--type", "web app", "--deploy-model", "prod-beta")
    finally:
        os.chmod(root / "Scope", 0o755)
    (root / DOCS[1]).write_text("# Owner rewrote the plan during the outage\n")
    h = sha(root / DOCS[1])
    rc, st, log = jrun("activate", root, "--name", "Beta", "--type", "web app", "--deploy-model", "prod-beta")
    need(sha(root / DOCS[1]) == h, "owner's mid-interruption edit was overwritten")
    need(st != "complete", f"owner-edited plan contradicts intake but run reported {st}")
    need("Beta" in text(root, "STATUS.md"), "STATUS not updated to Beta")
    return f"Alpha->Beta(interrupted{', mixed docs observed' if mixed else ''})->Gamma converges; resume converges; owner edit kept, status {st}"


def k8_deploy_authority(tmp):
    seen = []
    for label, extra in (("omitted", []), ("empty", ["--deploy-model", ""]), ("spaces", ["--deploy-model", "   "]),
                         ("tab", ["--deploy-model", "\t"])):
        base, root = fresh(tmp, "k8-" + label)
        rc, st, log = jrun("activate", root, "--name", "Deploy " + label, "--type", "web app", *extra)
        need(rc == 0, f"{label}: rc={rc}")
        assert_docs(root, "Deploy " + label, None)
        need(st != "complete", f"{label} deploy answer reported {st}")
        need("main=live" not in text(root, "STATUS.md") + text(root, DOCS[1]), f"{label}: live default written")
        need("UNRESOLVED" in text(root, DOCS[1]), f"{label}: plan does not carry UNRESOLVED")
        seen.append(f"{label}:{st}")
    base, root = fresh(tmp, "k8-clear")
    jrun("activate", root, "--name", "Clearable", "--type", "web app", "--deploy-model", "prod main=live")
    assert_docs(root, "Clearable", "prod main=live")
    rc, st, _ = jrun("activate", root, "--name", "Clearable", "--type", "web app", "--deploy-model", "")
    need(rc == 0, "clearing the deploy answer failed")
    assert_docs(root, "Clearable", None)
    need("main=live" not in text(root, "STATUS.md"), "cleared deploy answer still says main=live")
    need(st != "complete", f"cleared deploy reported {st}")
    base, root = fresh(tmp, "k8-main")
    rc, st, _ = jrun("activate", root, "--name", "Explicit", "--type", "web app", "--deploy-model", "main")
    need(rc == 0, "explicit deploy answer refused")
    assert_docs(root, "Explicit", "main")  # positive control: an owner answer is recorded verbatim
    return "omitted/empty/spaces/tab -> UNRESOLVED, not complete (" + ", ".join(seen) + \
           "); clear after confirmed -> UNRESOLVED; explicit 'main' recorded verbatim"


def k9_escape_refused(tmp):
    done = []

    def case(label, plant, args_extra=()):
        base, root = fresh(tmp, "k9-" + label)
        root.mkdir()
        plant(base, root)
        before = snap(base, exclude="proj")
        links = {r: v for r, v in snap(root).items() if v.startswith("link:")}
        rc, st, log = jrun("activate", root, "--name", "Escape " + label, "--deploy-model", "none", *args_extra)
        need(snap(base, exclude="proj") == before, f"{label}: outside tree changed")
        after_links = {r: v for r, v in snap(root).items() if v.startswith("link:")}
        need(all(after_links.get(r) == v for r, v in links.items()), f"{label}: owner link removed or retargeted")
        need(not (rc == 0 and st == "complete"), f"{label}: escape accepted as complete")
        done.append(f"{label}:rc={rc}/{st}")

    case("delivery-dir-link", lambda b, r: (r / "Delivery").symlink_to(b / "outside", target_is_directory=True))
    case("assets-dir-link", lambda b, r: (r / "Assets").symlink_to(b / "outside", target_is_directory=True))
    case("scope-dangling", lambda b, r: (r / "Scope").symlink_to(b / "outside" / "nowhere"))
    case("status-file-link", lambda b, r: (r / "STATUS.md").symlink_to(b / "outside" / "sentinel.txt"))
    case("plan-file-link", lambda b, r: ((r / "Scope").mkdir(),
                                          (r / DOCS[1]).symlink_to(b / "outside" / "sentinel.txt")))
    case("creds-dangling", lambda b, r: ((r / "Delivery").mkdir(),
                                          (r / DOCS[2]).symlink_to(b / "outside" / "new-creds.md")))
    case("journal-link", lambda b, r: (r / ".solaris-activation.json").symlink_to(b / "outside" / "sentinel.txt"))

    # planted temp-name aliases must not be written through, and activation still works
    base, root = fresh(tmp, "k9-temp")
    root.mkdir(); (root / "Scope").mkdir(); (root / "Delivery").mkdir()
    n = 0
    for d in DOCS + (".solaris-activation.json",):
        p = root / d
        for pat in (".{n}.tmp", "{n}.tmp", ".{n}.swp", "{n}~", ".{n}.new", "{n}.partial"):
            alias = p.parent / pat.format(n=p.name)
            target = base / "outside" / f"alias{n}.txt"
            target.write_text("ALIAS SENTINEL\n")
            alias.symlink_to(target); n += 1
    before = snap(base, exclude="proj")
    rc, st, log = jrun("activate", root, "--name", "Temp Alias", "--deploy-model", "none")
    need(snap(base, exclude="proj") == before, "a planted temp-name symlink was written through")
    need(rc == 0, f"activation with {n} planted aliases failed rc={rc}")
    assert_docs(root, "Temp Alias", "none")
    done.append(f"temp-aliases({n}):rc={rc}")

    # --within boundary escape creates nothing
    base, _ = fresh(tmp, "k9-within")
    allowed = base / "allowed"; allowed.mkdir()
    before = snap(base)
    rc, st, log = jrun("activate", str(allowed) + "/../escaped", "--name", "Esc", "--within", allowed)
    need(rc != 0 and snap(base) == before, f"--within escape not refused cleanly (rc={rc})")
    done.append(f"within-escape:rc={rc}")

    # .git symlinked to an outside repository
    base, root = fresh(tmp, "k9-gitlink")
    other = base / "outside" / "otherrepo"; _history_repo(other)
    root.mkdir(); (root / ".git").symlink_to(other / ".git", target_is_directory=True)
    g0 = git_state(other); before = snap(base / "outside")
    rc, st, log = jrun("activate", root, "--name", "Git Link", "--code", "--init-git", "--deploy-model", "none")
    need(git_state(other) == g0 and snap(base / "outside") == before, "outside repo reached through .git link changed")
    need(st != "complete", f".git link reported {st}")
    done.append(f"git-link:rc={rc}/{st}")
    return "; ".join(done)


def k10_secret_refused(tmp):
    for label, cred in (("location", f"system=github;username=bot;location={FAKE_TOKEN}"),
                        ("notes", f"system=github;username=bot;location=Vault/x;notes={FAKE_TOKEN}"),
                        ("username", f"system=github;username={FAKE_TOKEN};location=Vault/x")):
        base, root = fresh(tmp, "k10-" + label)
        rc, out, err = run("activate", root, "--name", "Secret", "--credential", cred)
        need(rc != 0, f"{label}: token-shaped credential accepted")
        need(FAKE_TOKEN not in out + err, f"{label}: token echoed")
        found = [r for r in (snap(root) if root.exists() else {}) if (root / r).is_file()
                 and FAKE_TOKEN in (root / r).read_text(errors="ignore")]
        need(not found, f"{label}: token persisted in {found}")
        need(not root.exists() or not any(root.iterdir()), f"{label}: files written despite refusal")
    base, root = fresh(tmp, "k10-ok")
    rc, out, err = run("activate", root, "--name", "Refs", "--credential", "system=aws;username=ci;location=Keychain/aws-ci")
    need(rc == 0 and "Keychain/aws-ci" in text(root, DOCS[2]), "valid reference control failed")
    return "token in location/notes/username refused, not echoed, nothing written; valid reference recorded"


def k11_concurrency(tmp):
    rounds = []
    for r in range(6):
        base, root = fresh(tmp, f"k11-{r}")
        names = [f"Racer{r}x{i}" for i in range(10)]
        # rounds 3-5 model a slow disk (15 ms per write event) so unserialized writers interleave
        env = clean_env({"M02_KILL_ROOT": str(base), "M02_SLOW_MS": "15", "PYTHONPATH": str(INJECT)} if r >= 3 else None)
        procs = [subprocess.Popen(CMD + ["activate", str(root), "--name", n, "--type", "web app", "--deploy-model", f"d-{n}"],
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env) for n in names]
        codes = [p.wait(timeout=120) for p in procs]
        need(any(c == 0 for c in codes), f"round {r}: no run succeeded {codes}")
        need(not (root / LOCKNAME).exists(), f"round {r}: lock left behind")
        st = text(root, "STATUS.md")
        winner = [n for n in names if f"# Project status: {n}" in st or f": {n}\n" in st]
        need(len(winner) == 1, f"round {r}: STATUS names {winner}")
        w = winner[0]
        for d in DOCS:
            need(w in text(root, d) and all(n not in text(root, d) for n in names if n != w),
                 f"round {r}: {d} disagrees with STATUS ({w})")
        assert_docs(root, w, f"d-{w}")
        rounds.append(f"{codes.count(0)}/10 ok")
    return "6 rounds x 10 concurrent runs (3 on a slowed disk): docs agree on one project each round (" + ", ".join(rounds) + ")"


CHECKS = [k1_clean_twice, k2_owner_docs, k3_git_and_outside, k4_unborn_and_worktree, k5_interrupt_resume,
          k6_sigkill_resume, k7_changed_intake_interruption, k8_deploy_authority, k9_escape_refused,
          k10_secret_refused, k11_concurrency]


def main(argv):
    global CMD
    if "--" not in argv:
        print(__doc__)
        return 2
    i = argv.index("--")
    opts, CMD = argv[:i], argv[i + 1:]
    only = None
    if "--only" in opts:
        only = set(opts[opts.index("--only") + 1].split(","))
    tmp = Path(tempfile.mkdtemp(prefix="m02-oracle-")).resolve()
    passed = failed = 0
    print(f"# m02_oracle candidate: {' '.join(CMD)}")
    try:
        for chk in CHECKS:
            key = chk.__name__.split("_")[0].upper()
            if only and key not in only:
                continue
            t0 = time.time()
            try:
                msg = chk(tmp)
                passed += 1
                print(f"PASS {chk.__name__} ({time.time() - t0:.1f}s): {msg}")
            except Fail as exc:
                failed += 1
                print(f"FAIL {chk.__name__}: {exc}")
            except Exception as exc:  # a crash in the candidate's output handling is a failure, never a skip
                failed += 1
                print(f"FAIL {chk.__name__}: {type(exc).__name__}: {str(exc)[:300]}")
            sys.stdout.flush()
    finally:
        for dirpath, dirnames, _ in os.walk(tmp):
            for d in dirnames:
                try:
                    os.chmod(os.path.join(dirpath, d), 0o755)
                except OSError:
                    pass
        shutil.rmtree(tmp, ignore_errors=True)
    total = passed + failed
    verdict = "ACCEPTS" if failed == 0 and total > 0 else "REJECTS"
    print(f"SUMMARY {passed}/{total} pass; oracle {verdict} candidate")
    return 0 if verdict == "ACCEPTS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
