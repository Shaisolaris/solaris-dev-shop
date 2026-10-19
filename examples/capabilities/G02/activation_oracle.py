#!/usr/bin/env python3
"""Adversarial activation oracle for G02 (stdlib only, synthetic data, disposable dirs).

Every check asserts real filesystem outcomes, so a candidate that does nothing,
echoes its input or only exits 0 fails. A missing or crashing candidate fails;
nothing is ever skipped into a pass.

Candidate interface (the adapter): a command prefix that accepts
  activate ROOT --name N [--type T] [--deploy-model D] [--credential "system=..;username=..;location=.."]
                [--code] [--init-git] [--json]
  resume ROOT [--json]
writes into ROOT and exits non-zero when it did not finish. The checks read files,
hashes and Git state; only O4 reads the --json "status" field, and only to require
that an inconsistent run is not reported as complete.

Usage: python activation_oracle.py -- <candidate command prefix...>
e.g.   python activation_oracle.py -- python3 employees/product-project/project-onboarding/activate.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DOCS = ("STATUS.md", "Scope/ROUND-PLAN.md", "Delivery/CREDENTIALS.md")
FOLDERS = ("Scope", "Development", "Delivery", "Assets")
TOKEN = "ghp_" + "Q7" * 18  # synthetic, shaped like a GitHub token, not a real credential
GIT = ["git", "-c", "user.name=Oracle", "-c", "user.email=oracle@example.invalid", "-c", "core.hooksPath=/dev/null"]


class Fail(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Fail(msg)


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def tree(root, skip_git=True):
    out = {}
    root = Path(root)
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if skip_git and (rel == ".git" or rel.startswith(".git/")):
            continue
        out[rel] = "link:" + os.readlink(p) if p.is_symlink() else sha(p) if p.is_file() else "dir"
    return out


def git(cwd, *args):
    return subprocess.run(GIT + ["-C", str(cwd), *args], capture_output=True, text=True)


def repo_state(path):
    gd = git(path, "rev-parse", "--absolute-git-dir").stdout.strip()
    idx = Path(gd) / "index"
    return {"refs": git(path, "for-each-ref", "--format=%(refname) %(objectname)").stdout,
            "head": git(path, "symbolic-ref", "-q", "HEAD").stdout + git(path, "rev-parse", "-q", "--verify", "HEAD").stdout,
            "log": git(path, "log", "--all", "--format=%H %s").stdout,
            "index": sha(idx) if idx.exists() else None}


class Oracle:
    def __init__(self, cmd, base):
        self.cmd, self.base, self.n = cmd, base, 0

    def run(self, *args, env=None):
        p = subprocess.run(self.cmd + [str(a) for a in args], capture_output=True, text=True, timeout=120,
                           env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1", **(env or {})))
        need("Traceback" not in p.stderr, "candidate crashed: " + p.stderr.strip()[-300:])
        return p

    def fresh(self, name):
        self.n += 1
        d = self.base / f"{self.n:02d}-{name}"
        d.mkdir()
        return d

    def docs_ok(self, root, name, deploy=None):
        for f in FOLDERS:
            need((root / f).is_dir() and not (root / f).is_symlink(), f"{f}/ was not created as a real directory")
        for d in DOCS:
            need((root / d).is_file(), f"{d} missing")
            need(name in (root / d).read_text(), f"{d} does not name the project {name!r}")
        if deploy is not None:
            need(f"DEPLOY-MODEL: {deploy}" in (root / "STATUS.md").read_text(), f"STATUS.md lacks 'DEPLOY-MODEL: {deploy}'")

    # O1 ------------------------------------------------------------------
    def o1_clean_twice(self):
        root = self.fresh("clean") / "proj"
        args = ["activate", root, "--name", "Orchid", "--type", "web app", "--deploy-model", "staging on merge",
                "--credential", "system=github;username=orchid-bot;location=Vault/Eng/GitHub"]
        p = self.run(*args)
        need(p.returncode == 0, f"first activation exit {p.returncode}")
        self.docs_ok(root, "Orchid", "staging on merge")
        creds = (root / "Delivery/CREDENTIALS.md").read_text()
        need("Vault/Eng/GitHub" in creds and "orchid-bot" in creds, "credential location/username not recorded")
        first = tree(root)
        p = self.run(*args)
        need(p.returncode == 0, f"second activation exit {p.returncode}")
        need(tree(root) == first, "second identical activation changed bytes")
        p = self.run("resume", root)
        need(p.returncode == 0 and tree(root) == first, "resume after complete run changed bytes or failed")
        return "two activations + resume byte-identical; docs, deploy line and credential row present"

    # O2 ------------------------------------------------------------------
    def o2_owner_files(self):
        root = self.fresh("owner") / "proj"
        (root / "Scope").mkdir(parents=True)
        (root / "Assets").mkdir()
        (root / "STATUS.md").write_text("Owner wrote this status by hand.\n")
        (root / "Scope/notes.txt").write_text("owner notes\n")
        (root / "Assets/logo.bin").write_bytes(bytes(range(256)) * 8)
        before = tree(root)
        p = self.run("activate", root, "--name", "Basil", "--type", "website", "--deploy-model", "manual")
        need(p.returncode == 0, f"exit {p.returncode}")
        after = tree(root)
        need(all(after.get(k) == v for k, v in before.items()), "a pre-existing owner file changed or vanished")
        for d in DOCS[1:]:
            need((root / d).is_file() and "Basil" in (root / d).read_text(), f"{d} not created alongside owner files")
        need("STATUS.md" in p.stdout, "the preserved STATUS.md conflict is not reported")
        return "3 owner files byte-identical; missing docs created; conflict reported"

    # O3 ------------------------------------------------------------------
    def o3_interrupt_resume(self):
        root = self.fresh("interrupt") / "proj"
        (root / "Scope").mkdir(parents=True)
        os.chmod(root / "Scope", 0o555)
        try:
            p = self.run("activate", root, "--name", "Cedar", "--type", "game", "--deploy-model", "owner uploads builds")
            need(p.returncode != 0, "a run that could not write Scope/ROUND-PLAN.md exited 0")
            need(not (root / "Scope/ROUND-PLAN.md").exists(), "unexpected ROUND-PLAN.md under a read-only folder")
        finally:
            os.chmod(root / "Scope", 0o755)
        p = self.run("resume", root)
        need(p.returncode == 0, f"resume exit {p.returncode}: {p.stdout.strip()}")
        self.docs_ok(root, "Cedar", "owner uploads builds")
        snap = tree(root)
        need(self.run("resume", root).returncode == 0 and tree(root) == snap, "second resume not stable")
        need(not list(root.rglob("*tmp*")), "temporary files left behind")
        return "real EACCES between writes -> non-zero; resume completes all docs; stable; no temp leftovers"

    # O4 ------------------------------------------------------------------
    def o4_changed_intake_during_interruption(self):
        root = self.fresh("changed") / "proj"
        need(self.run("activate", root, "--name", "Dahlia", "--type", "website", "--deploy-model", "manual").returncode == 0,
             "initial activation failed")
        os.chmod(root / "Scope", 0o555)
        try:
            p = self.run("activate", root, "--name", "Elder", "--json")
            need(p.returncode != 0, "interrupted rename exited 0")
            status = json.loads(p.stdout).get("status") if p.stdout.strip().startswith("{") else None
            need(status != "complete", "an inconsistent on-disk state was reported complete")
        finally:
            os.chmod(root / "Scope", 0o755)
        p = self.run("resume", root)
        need(p.returncode == 0, "resume after fixing the cause failed")
        self.docs_ok(root, "Elder", "manual")
        for d in DOCS:
            need("Dahlia" not in (root / d).read_text(), f"{d} still names the old project after resume")
        (root / "Scope/ROUND-PLAN.md").write_text("Owner rewrote the plan.\n")
        edited = sha(root / "Scope/ROUND-PLAN.md")
        p = self.run("activate", root, "--name", "Fennel", "--json")
        need(sha(root / "Scope/ROUND-PLAN.md") == edited, "owner-edited ROUND-PLAN.md was overwritten")
        need(json.loads(p.stdout).get("status") != "complete", "run with a preserved conflict reported complete")
        need("Fennel" in (root / "STATUS.md").read_text(), "tool-owned STATUS.md did not follow the new name")
        return "interrupted rename not complete; resume converges on new name; owner edit preserved and not complete"

    # O5 ------------------------------------------------------------------
    def o5_no_silent_live_authority(self):
        out = []
        for label, extra in (("blank", ["--deploy-model", "   "]), ("omitted", [])):
            root = self.fresh("deploy-" + label) / "proj"
            p = self.run("activate", root, "--name", "Ginger", "--type", "web app", *extra, "--json")
            need((root / "STATUS.md").is_file(), f"{label}: STATUS.md not written")
            text = (root / "STATUS.md").read_text()
            need("DEPLOY-MODEL: UNRESOLVED" in text, f"{label}: deploy model not recorded as UNRESOLVED")
            need("main=live" not in text and "DEPLOY-MODEL: main" not in text, f"{label}: a live default was recorded")
            need(json.loads(p.stdout).get("status") != "complete", f"{label}: unresolved deploy reported complete")
            out.append(label)
        return "blank and omitted deploy -> UNRESOLVED, not complete"

    # O6 ------------------------------------------------------------------
    def o6_outside_sentinels(self):
        base = self.fresh("escape")
        outside = base / "outside"
        outside.mkdir()
        for n in ("CREDENTIALS.md", "STATUS.md", "ROUND-PLAN.md"):
            (outside / n).write_text("SENTINEL " + n)
        root = base / "proj"
        root.mkdir()
        (root / "Delivery").symlink_to(outside, target_is_directory=True)
        for i in range(1, 50):  # predictable temp names a naive writer might use
            (root / f".STATUS.md.tmp.{i}").symlink_to(outside / "STATUS.md")
        (root / ".STATUS.md.tmp").symlink_to(outside / "STATUS.md")
        before = tree(outside)
        p = self.run("activate", root, "--name", "Hazel", "--deploy-model", "manual")
        need(tree(outside) == before, "an outside sentinel changed")
        need(p.returncode != 0, "a symlinked Delivery/ was accepted")
        need(not (root / "STATUS.md").exists(), "wrote into the project although it was blocked")
        (root / "Delivery").unlink()
        p = self.run("activate", root, "--name", "Hazel", "--deploy-model", "manual")
        need(p.returncode == 0, "activation did not succeed once the link was removed")
        self.docs_ok(root, "Hazel", "manual")
        need(tree(outside) == before, "an outside sentinel changed on the second run")
        return "Delivery link + 50 planted temp links: blocked, sentinels identical; succeeds after owner removes link"

    # O7 ------------------------------------------------------------------
    def o7_git_preserved(self):
        base = self.fresh("git")
        hist = base / "history"
        hist.mkdir()
        git(hist, "init", "-q", "--initial-branch=trunk")
        for i in range(2):
            (hist / f"f{i}.txt").write_text(str(i))
            git(hist, "add", ".")
            git(hist, "commit", "-qm", f"owner {i}")
        (hist / "wip.txt").write_text("staged")
        git(hist, "add", "wip.txt")
        unborn = base / "unborn"
        unborn.mkdir()
        git(unborn, "init", "-q", "--initial-branch=main")
        (unborn / "owner.txt").write_text("staged in unborn")
        git(unborn, "add", "owner.txt")
        nested = hist / "sub" / "proj"
        states = {p: repo_state(p) for p in (hist, unborn)}
        for root in (hist, unborn):
            p = self.run("activate", root, "--name", "Iris", "--deploy-model", "manual", "--code", "--init-git")
            need(p.returncode == 0, f"{root.name}: exit {p.returncode}")
            need((root / "STATUS.md").is_file(), f"{root.name}: STATUS.md not written")
        nested.parent.mkdir(parents=True)
        self.run("activate", nested, "--name", "Juniper", "--code", "--init-git")
        need((nested / "STATUS.md").is_file(), "nested project not activated")
        need(not (nested / ".git").exists(), "nested git init inside an existing repository")
        for path, st in states.items():
            need(repo_state(path) == st, f"{path.name}: refs, HEAD, history or index changed")
        return "history repo (2 commits + staged) and unborn staged repo: refs/HEAD/log/index identical; no nested init"

    # O8 ------------------------------------------------------------------
    def o8_secret_refused(self):
        root = self.fresh("secret") / "proj"
        p = self.run("activate", root, "--name", "Kale", "--credential", f"system=github;username=bot;location={TOKEN}")
        need(p.returncode != 0, "a token-shaped credential was accepted")
        need(TOKEN not in p.stdout + p.stderr, "the token was echoed")
        need(not root.exists() or not any(root.iterdir()), "files were written for a refused intake")
        return "token refused, not echoed, nothing written"

    # O9 ------------------------------------------------------------------
    def o9_concurrent(self):
        root = self.fresh("concurrent") / "proj"
        names = ["Laurel", "Myrtle", "Nutmeg", "Olive", "Poppy", "Quince"]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        procs = [subprocess.Popen(self.cmd + ["activate", str(root), "--name", n, "--type", "website",
                                              "--deploy-model", "manual"], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, env=env) for n in names]
        codes = [p.wait(timeout=120) for p in procs]
        need(0 in codes, f"no concurrent run finished: {codes}")
        p = self.run("resume", root)
        need(p.returncode == 0, "resume after concurrent runs failed")
        winners = [n for n in names if n in (root / "STATUS.md").read_text()]
        need(len(winners) == 1, f"STATUS.md names {winners}")
        self.docs_ok(root, winners[0], "manual")
        need(not [x for x in os.listdir(root) if "lock" in x or "tmp" in x], "lock or temp file left behind")
        return f"6 concurrent runs exit codes {codes}; all docs agree on {winners[0]}"

    # O10 -----------------------------------------------------------------
    def o10_scale(self):
        root = self.fresh("scale") / "proj"
        for i in range(3000):
            f = root / ("Development" if i % 2 else "Assets") / f"d{i % 50:02d}" / f"f{i:04d}.dat"
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(hashlib.sha256(str(i).encode()).digest() * 4)
        before = tree(root)
        t0 = time.monotonic()
        p = self.run("activate", root, "--name", "Rowan", "--type", "game", "--deploy-model", "manual")
        dt = time.monotonic() - t0
        need(p.returncode == 0, f"exit {p.returncode}")
        after = tree(root)
        need(all(after.get(k) == v for k, v in before.items()), "an owner file changed")
        self.docs_ok(root, "Rowan", "manual")
        return f"3000 owner files identical; activation {dt:.2f}s"

    # O11 -----------------------------------------------------------------
    def o11_ambiguous_deploy_and_corrupt_journal(self):
        """Blank-looking / disguised UNRESOLVED stay unresolved; deep journal is blocked, not a crash."""
        for label, dm in (
            ("hangul", "\u3164"),
            ("braille", "\u2800"),
            ("zw-unresolved", "\u200bUNRESOLVED"),
            ("fw-unresolved", "\uff35\uff2e\uff32\uff25\uff33\uff2f\uff2c\uff36\uff25\uff24"),
        ):
            root = self.fresh(f"amb-{label}") / "proj"
            p = self.run("activate", root, "--name", "Willow", "--type", "web app", "--deploy-model", dm, "--json")
            need(p.returncode == 0, f"{label}: unexpected exit {p.returncode}")
            data = json.loads(p.stdout)
            need(data.get("status") == "partial", f"{label}: status {data.get('status')}, expected partial")
            need("DEPLOY-MODEL: UNRESOLVED (no answer recorded" in (root / "STATUS.md").read_text(),
                 f"{label}: deploy line not unresolved")
        deep = self.fresh("deep-j") / "proj"
        deep.mkdir(parents=True)
        planted = deep / ".solaris-activation.json"
        planted.write_text("[" * 20000, encoding="utf-8")
        before = planted.read_bytes()
        p = self.run("activate", deep, "--name", "Deep", "--type", "web app", "--deploy-model", "main", "--json")
        need(p.returncode != 0, "deep journal was accepted")
        need("Traceback" not in p.stderr, "deep journal raised a traceback")
        data = json.loads(p.stdout) if p.stdout.strip().startswith("{") else {}
        need(data.get("status") == "blocked", f"deep journal status {data.get('status')}")
        need(planted.read_bytes() == before, "deep journal file was modified")
        names = sorted(x.name for x in deep.iterdir())
        need(names == [planted.name], f"extra files written beside corrupted journal: {names}")
        return "blank-looking/disguised UNRESOLVED -> partial; deep journal blocked, file preserved"


def main(argv):
    if "--" not in argv or argv.index("--") == len(argv) - 1:
        print(__doc__)
        return 2
    cmd = argv[argv.index("--") + 1:]
    exe = shutil.which(cmd[0]) or cmd[0]
    if not Path(exe).exists():
        print(f"FAIL candidate command not found: {cmd[0]}")
        return 1
    base = Path(tempfile.mkdtemp(prefix="g02-oracle-")).resolve()
    o = Oracle(cmd, base)
    checks = [m for m in sorted(dir(o)) if m[:1] == "o" and m[1:2].isdigit()]
    checks.sort(key=lambda m: int(m[1:].split("_")[0]))
    fails = 0
    try:
        for m in checks:
            try:
                print(f"PASS {m}: {getattr(o, m)()}")
            except Fail as e:
                fails += 1
                print(f"FAIL {m}: {e}")
            except Exception as e:  # a candidate that breaks the scenario fails it
                fails += 1
                print(f"FAIL {m}: {type(e).__name__}: {e}")
    finally:
        for p in base.rglob("*"):
            if p.is_dir() and not p.is_symlink():
                os.chmod(p, 0o755)
        shutil.rmtree(base, ignore_errors=True)
    print(f"SUMMARY {len(checks) - fails}/{len(checks)} pass; candidate {'ACCEPTED by oracle' if not fails else 'REJECTED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
