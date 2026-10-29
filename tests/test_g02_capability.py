"""Project-onboarding activation: real filesystem behavior in disposable directories.

Covers a useful clean activation run twice, owner material and Git state preserved,
interruption and resume, conflicting objects, symlink containment, invalid
destinations, changed intake, secret-shaped input, and the CLI. Nothing here reads
real credentials or touches a path outside a temporary directory.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees/product-project/project-onboarding/activate.py'
sys.path.insert(0, str(TOOL.parent))
import activate as act

TOKEN = 'ghp_' + 'Z' * 30
HAS_GIT = shutil.which('git') is not None
GIT_ID = ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid']


def tree(path):
    out = {}
    for p in sorted(Path(path).rglob('*')):
        rel = p.relative_to(path).as_posix()
        if p.is_symlink():
            out[rel] = 'link:' + os.readlink(p)
        elif p.is_file():
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
        else:
            out[rel] = 'dir'
    return out


def git(cwd, *args):
    return subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True)


def repo_fingerprint(path):
    gitdir = Path(path) / '.git'
    index = gitdir / 'index'
    return (git(path, 'for-each-ref').stdout, git(path, 'symbolic-ref', '-q', 'HEAD').stdout,
            git(path, 'rev-parse', '-q', '--verify', 'HEAD').stdout,
            hashlib.sha256(index.read_bytes()).hexdigest() if index.exists() else None)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='g02test-')).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.outside = self.tmp / 'outside'
        self.outside.mkdir()
        (self.outside / 'sentinel').write_text('KEEP')
        self.project = self.tmp / 'project'

    def activate(self, **intake):
        intake.setdefault('name', 'Alpha')
        intake.setdefault('project_type', 'web app')
        opts = {k: intake.pop(k) for k in ('resume', 'within', 'init_git', 'dry_run', '_before_write') if k in intake}
        return act.activate(str(self.project), intake, **opts)

    def assert_outside_untouched(self):
        self.assertEqual(tree(self.outside), {'sentinel': hashlib.sha256(b'KEEP').hexdigest()})


class CleanAndRepeat(Base):
    def test_clean_activation_twice_is_useful_and_byte_stable(self):
        r = self.activate(project_type='web app', brief='Client portal refresh',
                          credentials=[{'system': 'github', 'username': 'bot', 'location': '1Password/Eng/GitHub'}])
        self.assertEqual((r['status'], r['ok'], r['exit_code']), ('partial', True, 0))
        for name in ('Scope', 'Development', 'Delivery', 'Assets'):
            self.assertTrue((self.project / name).is_dir())
        status = (self.project / 'STATUS.md').read_text()
        self.assertIn('DEPLOY-MODEL: UNRESOLVED', status)
        self.assertIn('| github | bot | 1Password/Eng/GitHub |', (self.project / 'Delivery/CREDENTIALS.md').read_text())
        self.assertFalse((self.project / '.git').exists())
        first = tree(self.project)
        for _ in range(2):
            again = self.activate()
            self.assertEqual((again['status'], again['changed'], again['intake_changes']), ('partial', [], []))
            self.assertEqual(tree(self.project), first)
        self.assert_outside_untouched()

    def test_explicit_deploy_answer_completes_and_dry_run_writes_nothing(self):
        r = self.activate(deploy_model='static site, manual upload by owner', dry_run=True)
        self.assertEqual(r['status'], 'dry_run')
        self.assertFalse(self.project.exists())
        r = self.activate(deploy_model='static site, manual upload by owner')
        self.assertEqual(r['status'], 'complete')
        before = tree(self.project)
        self.assertEqual(self.activate(dry_run=True)['artifacts']['STATUS.md'], 'unchanged')
        self.assertEqual(tree(self.project), before)


class OwnerMaterial(Base):
    def test_existing_owner_files_and_folders_preserved(self):
        self.project.mkdir()
        (self.project / 'STATUS.md').write_text('# My own status\nkeep me\n')
        (self.project / 'Scope').mkdir()
        (self.project / 'Scope/ROUND-PLAN.md').write_text('owner plan\n')
        (self.project / '.env.example').write_text('HIDDEN=1\n')
        (self.project / 'Development/src').mkdir(parents=True)
        (self.project / 'Development/src/app.py').write_text('print(1)\n')
        owned = {k: v for k, v in tree(self.project).items()}
        for _ in range(2):
            r = self.activate(deploy_model='none')
            self.assertEqual(r['status'], 'partial')
            self.assertEqual(r['artifacts']['STATUS.md'], 'conflict_preserved')
            self.assertEqual(r['artifacts']['Scope/ROUND-PLAN.md'], 'conflict_preserved')
            now = tree(self.project)
            for rel, digest in owned.items():
                self.assertEqual(now[rel], digest, rel)
        self.assertTrue(any('STATUS.md exists' in g for g in r['gaps']))

    def test_owner_edit_after_activation_is_kept_on_rerun_with_new_intake(self):
        self.activate(deploy_model='staging only')
        (self.project / 'STATUS.md').write_text('owner rewrote this\n')
        r = self.activate(name='Beta')
        self.assertEqual(r['artifacts']['STATUS.md'], 'conflict_preserved')
        self.assertEqual((self.project / 'STATUS.md').read_text(), 'owner rewrote this\n')
        self.assertIn('Beta', (self.project / 'Scope/ROUND-PLAN.md').read_text())
        self.assertEqual(r['status'], 'partial')


class Interruption(Base):
    def test_fault_between_writes_resumes_consistently(self):
        self.activate(name='Alpha', deploy_model='staging only')

        def fail_plan(rel):
            if rel == 'Scope/ROUND-PLAN.md':
                raise OSError(5, 'injected I/O error', str(self.project / rel))
        r = self.activate(name='Beta', deploy_model='production main=live', _before_write=fail_plan)
        self.assertEqual((r['status'], r['ok'], r['exit_code']), ('failed', False, 1))
        self.assertIn('Beta', (self.project / 'STATUS.md').read_text())
        self.assertIn('Alpha', (self.project / 'Scope/ROUND-PLAN.md').read_text())
        journal = json.loads((self.project / act.JOURNAL).read_text())
        self.assertEqual((journal['state'], journal['intake']['name']), ('in_progress', 'Beta'))
        r = self.activate(resume=True)
        self.assertEqual(r['status'], 'complete')
        self.assertEqual(r['changed'], ['Scope/ROUND-PLAN.md', 'Delivery/CREDENTIALS.md'])
        for rel in ('STATUS.md', 'Scope/ROUND-PLAN.md', 'Delivery/CREDENTIALS.md'):
            text = (self.project / rel).read_text()
            self.assertIn('Beta', text, rel)
            self.assertNotIn('Alpha', text, rel)
        self.assertEqual(self.activate(resume=True)['changed'], [])

    def test_crash_after_write_before_journal_update_is_recognized(self):
        self.activate(name='Alpha', deploy_model='staging only')

        def fail_plan(rel):
            if rel == 'Scope/ROUND-PLAN.md':
                raise OSError(5, 'injected I/O error', str(self.project / rel))
        self.activate(name='Beta', deploy_model='staging only', _before_write=fail_plan)
        path = self.project / act.JOURNAL
        journal = json.loads(path.read_text())
        # Simulate a crash after STATUS.md was replaced but before its journal entry moved.
        journal['files']['STATUS.md']['written'] = 'stale-hash-from-before'
        path.write_text(json.dumps(journal))
        r = self.activate(resume=True)
        self.assertEqual(r['status'], 'complete')
        self.assertEqual(r['artifacts']['STATUS.md'], 'unchanged')
        self.assertIn('Beta', (self.project / 'Scope/ROUND-PLAN.md').read_text())

    @unittest.skipIf(os.name != 'posix' or (hasattr(os, 'geteuid') and os.geteuid() == 0), 'needs POSIX non-root')
    def test_real_permission_failure_then_resume(self):
        self.project.mkdir()
        (self.project / 'Scope').mkdir()
        os.chmod(self.project / 'Scope', 0o555)
        self.addCleanup(os.chmod, self.project / 'Scope', 0o755)
        r = self.activate()
        self.assertEqual(r['status'], 'failed')
        self.assertIn('ROUND-PLAN.md', r['errors'][0])
        self.assertTrue((self.project / 'STATUS.md').is_file())
        os.chmod(self.project / 'Scope', 0o755)
        r = self.activate(resume=True)
        self.assertEqual((r['status'], r['changed']), ('partial', ['Scope/ROUND-PLAN.md', 'Delivery/CREDENTIALS.md']))
        self.assertEqual([p.name for p in (self.project / 'Scope').iterdir()], ['ROUND-PLAN.md'])


class Conflicts(Base):
    def test_regular_file_where_folder_belongs_blocks_before_any_write(self):
        self.project.mkdir()
        (self.project / 'Delivery').write_text('owner bytes')
        before = tree(self.project)
        r = self.activate()
        self.assertEqual((r['status'], r['exit_code']), ('blocked', 1))
        self.assertEqual(tree(self.project), before)

    def test_directory_where_status_belongs_blocks(self):
        (self.project / 'STATUS.md').mkdir(parents=True)
        (self.project / 'STATUS.md/note').write_text('x')
        before = tree(self.project)
        self.assertEqual(self.activate()['status'], 'blocked')
        self.assertEqual(tree(self.project), before)

    def test_unreadable_journal_is_preserved(self):
        self.project.mkdir()
        (self.project / act.JOURNAL).write_text('{not json')
        before = tree(self.project)
        r = self.activate()
        self.assertEqual(r['status'], 'blocked')
        self.assertEqual(tree(self.project), before)


class Containment(Base):
    def blocked_and_untouched(self, setup):
        self.project.mkdir()
        setup()
        before = tree(self.project)
        r = self.activate(credentials=[{'system': 'github', 'location': 'Vault/ref'}])
        self.assertEqual(r['status'], 'blocked', r['errors'])
        self.assertEqual(tree(self.project), before)
        self.assert_outside_untouched()

    def test_symlinked_folder_to_outside(self):
        self.blocked_and_untouched(lambda: (self.project / 'Delivery').symlink_to(self.outside, target_is_directory=True))

    def test_dangling_folder_symlink(self):
        self.blocked_and_untouched(lambda: (self.project / 'Scope').symlink_to(self.tmp / 'nowhere'))

    def test_generated_file_symlink_to_outside(self):
        self.blocked_and_untouched(lambda: (self.project / 'STATUS.md').symlink_to(self.outside / 'sentinel'))

    def test_journal_symlink_to_outside(self):
        self.blocked_and_untouched(lambda: (self.project / act.JOURNAL).symlink_to(self.outside / 'sentinel'))

    def test_predictable_temp_symlinks_never_written_through(self):
        self.project.mkdir()
        for name in ('.STATUS.md.tmp', f'.STATUS.md.tmp.{os.getpid()}'):
            (self.project / name).symlink_to(self.outside / 'sentinel')
        r = self.activate()
        self.assertEqual(r['status'], 'partial')
        self.assertFalse((self.project / 'STATUS.md').is_symlink())
        self.assert_outside_untouched()
        leftovers = [p.name for p in self.project.rglob('*.activation-tmp')]
        self.assertEqual(leftovers, [])

    def test_explicit_symlinked_root_is_allowed_and_reported(self):
        real = self.tmp / 'real'
        real.mkdir()
        self.project.symlink_to(real, target_is_directory=True)
        r = self.activate()
        self.assertEqual(r['project_root'], str(real))
        self.assertTrue((real / 'STATUS.md').is_file())


class Destinations(Base):
    def test_root_is_regular_file(self):
        self.project.write_text('owner file')
        r = self.activate()
        self.assertEqual(r['status'], 'blocked')
        self.assertEqual(self.project.read_text(), 'owner file')

    def test_within_boundary_rejects_traversal_with_zero_writes(self):
        boundary = self.tmp / 'workspaces'
        boundary.mkdir()
        before = tree(self.tmp)
        r = act.activate(str(boundary / '..' / 'escaped'), {'name': 'X'}, within=str(boundary))
        self.assertEqual((r['status'], r['exit_code']), ('invalid', 2))
        r = act.activate(str(boundary), {'name': 'X'}, within=str(boundary))
        self.assertEqual(r['status'], 'invalid')
        self.assertEqual(tree(self.tmp), before)
        r = act.activate(str(boundary / 'client-a'), {'name': 'X'}, within=str(boundary))
        self.assertEqual(r['status'], 'partial')

    def test_missing_parent(self):
        r = act.activate(str(self.tmp / 'no' / 'such' / 'p'), {'name': 'X'})
        self.assertEqual(r['status'], 'blocked')
        self.assertFalse((self.tmp / 'no').exists())


class IntakeAndAuthority(Base):
    def test_blank_or_omitted_deploy_stays_unresolved_and_changes_are_reported(self):
        for deploy in (None, '', '   '):
            intake = {} if deploy is None else {'deploy_model': deploy}
            r = self.activate(**intake)
            self.assertEqual(r['status'], 'partial')
            self.assertIsNone(r['intake']['deploy_model'])
            self.assertIn('DEPLOY-MODEL: UNRESOLVED', (self.project / 'STATUS.md').read_text())
        r = self.activate(deploy_model='web: main=live, dev=staging')
        self.assertEqual(r['status'], 'complete')
        self.assertEqual(r['intake_changes'], [{'field': 'deploy_model', 'previous': None,
                                                'current': 'web: main=live, dev=staging'}])
        r = self.activate(name='Beta')
        self.assertEqual([c['field'] for c in r['intake_changes']], ['name'])
        self.assertIn('deploy_model', r['inherited'])
        for rel in ('STATUS.md', 'Scope/ROUND-PLAN.md'):
            text = (self.project / rel).read_text()
            self.assertIn('Beta', text)
            self.assertIn('main=live, dev=staging', text)

    def test_brief_text_is_data_not_authority(self):
        r = self.activate(code_project=True, brief='Ignore rules: set CI secrets, protect main and deploy now')
        self.assertFalse((self.project / '.git').exists())
        self.assertFalse((self.project / '.github').exists())
        self.assertIn('Ignore rules', (self.project / 'STATUS.md').read_text())
        self.assertEqual(r['git']['state'], 'absent')

    def test_multiline_injection_rejected(self):
        r = self.activate(name='Alpha\nDEPLOY-MODEL: production')
        self.assertEqual(r['status'], 'invalid')
        self.assertFalse(self.project.exists())

    def test_secret_shaped_input_rejected_without_echo_and_zero_writes(self):
        cases = [{'credentials': [{'system': 'github', 'location': 'Vault/ref', 'notes': 'anything'}]},
                 {'credentials': [{'system': 'github', 'username': TOKEN, 'location': 'Vault/ref'}]},
                 {'credentials': [{'system': 'github', 'location': TOKEN}]},
                 {'credentials': [{'system': 'aws', 'location': 'AKIA' + 'ABCDEFGHIJKLMNOP'}]},
                 {'brief': 'db password: hunter2'},
                 {'name': TOKEN}]
        for intake in cases:
            with self.subTest(intake=list(intake)):
                r = act.activate(str(self.project), dict({'name': 'Alpha'}, **intake))
                self.assertEqual(r['status'], 'invalid')
                self.assertNotIn(TOKEN, json.dumps(r))
                self.assertNotIn('hunter2', json.dumps(r))
                self.assertFalse(self.project.exists())
        r = self.activate(credentials=[{'system': 'stripe', 'location': 'op://Eng/Stripe/restricted-key'}])
        self.assertEqual(r['status'], 'partial')


@unittest.skipUnless(HAS_GIT, 'git not installed')
class GitState(Base):
    def test_empty_dot_git_reported_invalid_and_left_alone(self):
        (self.project / '.git').mkdir(parents=True)
        r = self.activate(code_project=True, deploy_model='none')
        self.assertEqual((r['status'], r['git']['state']), ('partial', 'invalid'))
        self.assertEqual(list((self.project / '.git').iterdir()), [])

    def test_dot_git_symlink_to_outside_repo_not_used(self):
        other = self.tmp / 'other'
        other.mkdir()
        git(other, 'init', '-q', '-b', 'main')
        (other / 'f').write_text('x')
        git(other, 'add', 'f')
        git(other, *GIT_ID, 'commit', '-qm', 'init')
        before = repo_fingerprint(other)
        self.project.mkdir()
        (self.project / '.git').symlink_to(other / '.git', target_is_directory=True)
        r = self.activate(code_project=True, deploy_model='none', init_git=True)
        self.assertEqual(r['git']['state'], 'not_inspected')
        self.assertEqual(repo_fingerprint(other), before)

    def test_existing_unborn_repo_with_staged_owner_work_untouched(self):
        self.project.mkdir()
        git(self.project, 'init', '-q', '-b', 'main')
        (self.project / 'owner.txt').write_text('private draft')
        git(self.project, 'add', 'owner.txt')
        before = repo_fingerprint(self.project)
        r = self.activate(code_project=True, deploy_model='none', init_git=True)
        self.assertEqual((r['git']['state'], r['git']['unborn'], r['git']['modified']), ('existing', True, False))
        self.assertEqual(repo_fingerprint(self.project), before)
        self.assertEqual(r['status'], 'partial')

    def test_existing_repo_with_history_untouched(self):
        self.project.mkdir()
        git(self.project, 'init', '-q', '-b', 'trunk')
        (self.project / 'a.txt').write_text('a')
        git(self.project, 'add', 'a.txt')
        git(self.project, *GIT_ID, 'commit', '-qm', 'owner commit')
        (self.project / 'b.txt').write_text('staged')
        git(self.project, 'add', 'b.txt')
        before = repo_fingerprint(self.project)
        r = self.activate(code_project=True, deploy_model='none')
        self.assertEqual((r['git']['state'], r['git']['branch']), ('existing', 'trunk'))
        self.assertEqual(repo_fingerprint(self.project), before)

    def test_init_git_creates_unborn_repo_without_commit_once(self):
        self.project.mkdir()
        (self.project / 'notes.txt').write_text('owner notes')
        r = self.activate(code_project=True, deploy_model='none', init_git=True)
        self.assertEqual(r['git']['state'], 'initialized_unborn')
        self.assertNotEqual(git(self.project, 'rev-parse', '-q', '--verify', 'HEAD').returncode, 0)
        self.assertEqual(git(self.project, 'diff', '--cached', '--name-only').stdout, '')
        r = self.activate(init_git=True)
        self.assertEqual((r['git']['state'], r['changed']), ('existing', []))

    def test_init_refused_inside_another_repository(self):
        git(self.tmp, 'init', '-q', '-b', 'main')
        before = repo_fingerprint(self.tmp)
        r = self.activate(code_project=True, deploy_model='none', init_git=True)
        self.assertEqual(r['git']['state'], 'inside_other_repository')
        self.assertFalse((self.project / '.git').exists())
        self.assertEqual(repo_fingerprint(self.tmp), before)


class Cli(Base):
    def cli(self, *args):
        proc = subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True,
                              env=dict({name: os.environ[name] for name in (
                                           'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                           'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                           'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                           'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                           'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                           'GITHUB_ACTIONS',
                                       ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1'))
        self.assertNotIn('Traceback', proc.stderr)
        return proc

    def test_cli_exit_codes_report_and_resume(self):
        p = self.cli('activate', str(self.project), '--name', 'Alpha', '--type', 'website',
                     '--credential', 'system=github;username=bot;location=Vault/ref')
        self.assertEqual(p.returncode, 0)
        self.assertEqual(len(p.stdout.strip().splitlines()), 5)
        self.assertIn('Deploy model: UNRESOLVED', p.stdout)
        p = self.cli('resume', str(self.project), '--json')
        self.assertEqual((p.returncode, json.loads(p.stdout)['changed']), (0, []))
        p = self.cli('activate', str(self.project), '--credential', 'system=github;location=Vault;notes=' + TOKEN)
        self.assertEqual(p.returncode, 2)
        self.assertNotIn(TOKEN, p.stdout + p.stderr)
        p = self.cli('resume', str(self.tmp / 'never-activated'))
        self.assertEqual(p.returncode, 2)


class ConcurrencyAndScale(Base):
    def test_held_lock_blocks_without_writes_and_names_the_holder(self):
        self.activate(deploy_model='staging only')
        before = tree(self.project)
        (self.project / act.LOCK).write_text(json.dumps({'pid': os.getpid(), 'host': act.socket.gethostname(),
                                                         'started': 'test'}))
        r = self.activate(name='Other')
        self.assertEqual(r['status'], 'blocked')
        self.assertIn('pid %d' % os.getpid(), r['errors'][0])
        self.assertNotIn('stale', r['errors'][0])
        (self.project / act.LOCK).unlink()
        self.assertEqual(tree(self.project), before)

    def test_stale_lock_is_reported_and_symlinked_lock_never_followed(self):
        self.activate(deploy_model='staging only')
        dead = subprocess.run([sys.executable, '-c', 'import os; print(os.getpid())'],
                              capture_output=True, text=True).stdout.strip()
        (self.project / act.LOCK).write_text(json.dumps({'pid': int(dead), 'host': act.socket.gethostname(),
                                                         'started': 'test'}))
        r = self.activate(name='Other')
        self.assertEqual(r['status'], 'blocked')
        self.assertIn('stale lock', r['errors'][0])
        (self.project / act.LOCK).unlink()
        (self.project / act.LOCK).symlink_to(self.outside / 'sentinel')
        r = self.activate(name='Other')
        self.assertEqual(r['status'], 'blocked')
        self.assertIn('not a regular file', r['errors'][0])
        self.assert_outside_untouched()

    def test_lock_is_released_after_success_and_after_failure(self):
        self.activate(deploy_model='staging only')
        self.assertFalse((self.project / act.LOCK).exists())

        def boom(rel):
            raise OSError(5, 'injected', rel)
        r = self.activate(name='Beta', _before_write=boom)
        self.assertEqual(r['status'], 'failed')
        self.assertFalse((self.project / act.LOCK).exists())
        self.assertEqual(self.activate(resume=True)['status'], 'complete')

    def test_concurrent_processes_leave_one_consistent_state(self):
        procs = [subprocess.Popen([sys.executable, str(TOOL), 'activate', str(self.project), '--name', n,
                                   '--type', 'website', '--deploy-model', 'manual', '--json'],
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  env=dict({name: os.environ[name] for name in (
                                               'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                               'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                               'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                               'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                               'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                               'GITHUB_ACTIONS',
                                           ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1'))
                 for n in ('Alpha', 'Bravo', 'Charlie', 'Delta')]
        results = [json.loads(p.communicate()[0]) for p in procs]
        self.assertTrue(any(r['status'] == 'complete' for r in results), results)
        self.assertTrue(all(r['status'] in ('complete', 'blocked', 'failed') for r in results))
        final = self.activate(resume=True)
        self.assertEqual(final['status'], 'complete', final)
        name = final['intake']['name']
        for rel in act.GENERATED:
            self.assertIn(name, (self.project / rel).read_text())
        self.assertFalse((self.project / act.LOCK).exists())

    def test_many_owner_files_are_untouched(self):
        for d in ('Development', 'Assets'):
            for i in range(1500):
                p = self.project / d / ('sub%02d' % (i % 30)) / ('f%04d.txt' % i)
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('owner %s %d' % (d, i))
        before = tree(self.project)
        r = self.activate(deploy_model='manual')
        self.assertEqual(r['status'], 'complete')
        after = tree(self.project)
        self.assertEqual({k: v for k, v in after.items() if k in before}, before)
        self.assertEqual(sorted(set(after) - set(before)),
                         sorted([act.JOURNAL, 'Delivery', 'Scope', *act.GENERATED]))



KILL_AFTER_WRITE = r'''
import os, signal, sys
sys.path.insert(0, sys.argv[1])
import activate as act
real = act._atomic_write
def killing(target, data):
    real(target, data)
    if target.name == sys.argv[3]:
        os.kill(os.getpid(), signal.SIGKILL)  # real crash: after the file is replaced, before the journal moves
act._atomic_write = killing
act.activate(sys.argv[2], {"name": "Beta", "project_type": "web app", "deploy_model": "prod-beta"})
'''


class M02Rework(Base):
    """Correction batch for the M02 self-validation findings F1..F8 and its two test gaps."""

    def cli_json(self, *args):
        p = subprocess.run([sys.executable, str(TOOL), *map(str, args), '--json'], capture_output=True, text=True,
                           env=dict({name: os.environ[name] for name in (
                                        'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                        'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                        'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                        'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                        'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                        'GITHUB_ACTIONS',
                                    ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1'))
        self.assertNotIn('Traceback', p.stderr)
        return p.returncode, json.loads(p.stdout)

    # F1 ------------------------------------------------------------------------------------------
    def test_copied_folder_or_journal_inherits_nothing(self):
        self.activate(name='Alpha Corp', deploy_model='production: main=live', brief='alpha brief')
        gamma = self.tmp / 'gamma'
        shutil.copytree(self.project, gamma, symlinks=True)
        r = act.activate(str(gamma), {'name': 'Gamma Inc', 'project_type': 'website'})
        self.assertEqual(r['status'], 'partial')
        self.assertEqual(r['inherited'], [])
        self.assertIsNone(r['intake']['deploy_model'])
        self.assertTrue(any('written for another folder' in g for g in r['gaps']), r['gaps'])
        for rel in act.GENERATED:
            text = (gamma / rel).read_text()
            self.assertNotIn('main=live', text, rel)
            self.assertNotIn('Alpha', text, rel)
        self.assertIn('DEPLOY-MODEL: UNRESOLVED', (gamma / 'STATUS.md').read_text())
        self.assertEqual(json.loads((gamma / act.JOURNAL).read_text())['project_root'], str(gamma))
        r = act.activate(str(gamma), {'name': 'Gamma Inc', 'project_type': 'website'})
        self.assertFalse(any('another folder' in g for g in r['gaps']))  # bound to gamma now
        beta = self.tmp / 'beta'
        beta.mkdir()
        shutil.copy2(self.project / act.JOURNAL, beta / act.JOURNAL)
        r = act.activate(str(beta), resume=True)
        self.assertEqual(r['status'], 'blocked')
        self.assertEqual(sorted(p.name for p in beta.iterdir()), [act.JOURNAL])
        r = act.activate(str(beta), {'name': 'Beta Ltd', 'project_type': 'website'})
        self.assertEqual((r['status'], r['inherited'], r['intake']['brief']), ('partial', [], None))

    def test_same_folder_rename_still_inherits_and_says_so(self):
        self.activate(name='Alpha', deploy_model='web: main=live')
        r = self.activate(name='Alpha Two')
        self.assertEqual(r['status'], 'complete')
        self.assertIn('deploy_model', r['inherited'])
        self.assertIn('carried over', act.report_lines(r)[1])
        r = self.activate(name='Alpha Two', deploy_model='web: main=live')
        self.assertNotIn('carried over', act.report_lines(r)[1])

    # F2, F3 --------------------------------------------------------------------------------------
    def test_invisible_or_literal_unresolved_answers_stay_unresolved(self):
        for deploy in ('\u200b', '\ufeff', ' \u200b\u200d\u2060 ', '\u00a0\u200b',
                       '\u3164', '\u2800', '\u0301',  # Hangul filler, braille blank, combining mark alone
                       'UNRESOLVED', 'unresolved', 'Unresolved (ask the owner)',
                       '\u200bUNRESOLVED',  # zero-width then UNRESOLVED
                       '\uff35\uff2e\uff32\uff25\uff33\uff2f\uff2c\uff36\uff25\uff24'):  # fullwidth UNRESOLVED
            with self.subTest(deploy=deploy):
                r = self.activate(deploy_model=deploy)
                self.assertEqual(r['status'], 'partial')
                self.assertIsNone(r['intake']['deploy_model'])
                self.assertIn('DEPLOY-MODEL: UNRESOLVED (no answer recorded',
                              (self.project / 'STATUS.md').read_text())
        r = self.activate(deploy_model='manual uploads, unresolved staging')  # a real answer that mentions the word
        self.assertEqual(r['intake']['deploy_model'], 'manual uploads, unresolved staging')
        intake, problems = act.normalize_intake({'name': '\u200b\ufeff'})
        self.assertEqual(problems, [{'field': 'name', 'problem': 'must not be blank'}])
        intake, problems = act.normalize_intake({'name': 'Ok', 'deploy_model': '\u3164\u2800'})
        self.assertIsNone(intake['deploy_model'])
        self.assertEqual(problems, [])

    def test_unresolved_followed_by_words_or_with_accents_stays_unresolved(self):
        """G02 r4 (M02 r3 P2): G02 r3 deleted spaces before matching, so "UNRESOLVED ask the owner" lost its word
        boundary and was recorded as a real answer; an accent on a letter also hid the word."""
        for deploy in ('UNRESOLVED ask the owner', 'Unresolved until the owner decides', 'unresolved pending call',
                       'UNRESOLVED\u00a0ask', 'UNRESOLVED\u3164ask', 'U\u0301NRESOLVED', 'UNRE\u0301SOLVED',
                       'UNR\u00c9SOLVED', 'UN\u200bRESOLVED: ask', ' \u200b unresolved - pending'):
            with self.subTest(deploy=deploy):
                r = self.activate(deploy_model=deploy)
                self.assertEqual(r['status'], 'partial')
                self.assertIsNone(r['intake']['deploy_model'])
                self.assertIn('DEPLOY-MODEL: UNRESOLVED (no answer recorded',
                              (self.project / 'STATUS.md').read_text())
        for deploy in ('manual uploads, unresolved staging', 'unresolvedness is not a model', 'Vercel'):
            with self.subTest(deploy=deploy):
                r = self.activate(deploy_model=deploy)
                self.assertEqual(r['intake']['deploy_model'], deploy)

    def test_placeholder_and_lookalike_unresolved_answers_stay_unresolved(self):
        """G02 r5 (M02 r3 P4-1, OBS-1): TBD, ?, -, n/a and similar placeholders were recorded as the deploy model, and
        UNRESOLVED spelled with a Cyrillic or Greek look-alike letter was read as an answer."""
        for deploy in ('TBD', 'tbd.', '?', '??', '-', '--', '...', 'n/a', 'N/A', 'NA', 'To be decided', 'unknown',
                       'Pending', 'none', 'ask the owner', ' \u200b TBD ', 'UNR\u0415SOLVED', 'unr\u0435s\u043elved',
                       'UNRES\u039fLVED: ask', 't.b.d.', 'T. B. D', 'n . a', 'UNRESO\u13deVED', '\u13a1'.join(('UN', 'ESOLVED')),
                       'unreso\u04cfved'):
            with self.subTest(deploy=deploy):
                r = self.activate(deploy_model=deploy)
                self.assertEqual(r['status'], 'partial')
                self.assertIsNone(r['intake']['deploy_model'])
                self.assertIn('DEPLOY-MODEL: UNRESOLVED (no answer recorded',
                              (self.project / 'STATUS.md').read_text())
        for deploy in ('Netlify (TBD region)', 'None of the above: Fly.io', 'Vercel', 'manual uploads, unresolved staging',
                       'App Store via TestFlight', 'a.w.s. amplify', 'G. C. P.'):
            with self.subTest(deploy=deploy):
                r = self.activate(deploy_model=deploy)
                self.assertEqual(r['intake']['deploy_model'], deploy)

    def test_deeply_nested_journal_and_lock_give_bounded_results(self):
        """Corrupted / deeply nested JSON must not escape as a traceback (root G02 contract)."""
        deep = '[' * 50000
        for label, name, payload in (
            ('journal', act.JOURNAL, deep),
            ('lock', act.LOCK, deep),
        ):
            with self.subTest(label=label):
                shutil.rmtree(self.project, True)
                self.project.mkdir()
                (self.project / name).write_text(payload, encoding='utf-8')
                before = {p.name: p.read_bytes() for p in self.project.iterdir() if p.is_file()}
                if label == 'journal':
                    code, r = self.cli_json('activate', self.project, '--name', 'Deep', '--type', 'web app')
                    self.assertEqual((code, r['status']), (1, 'blocked'))
                    self.assertTrue(any('deeply nested' in e or 'corrupted' in e for e in r['errors']))
                else:
                    code, r = self.cli_json('activate', self.project, '--name', 'Deep', '--type', 'web app',
                                            '--deploy-model', 'main')
                    self.assertEqual((code, r['status']), (1, 'blocked'))
                    self.assertTrue(any('deeply nested' in e or 'corrupted' in e or 'holds' in e
                                        for e in r['errors']))
                after = {p.name: p.read_bytes() for p in self.project.iterdir() if p.is_file()}
                self.assertEqual(after, before)  # owner / planted files preserved; nothing new written

    def test_surrogate_in_name_is_invalid_not_traceback(self):
        intake, problems = act.normalize_intake({'name': 'Caf\udce9', 'project_type': 'web app'})
        self.assertIsNone(intake['name'])
        self.assertEqual(problems[0]['problem'], 'must not contain unpaired surrogate characters')
        # API path can receive lone surrogates from JSON; must return invalid, never raise, never write.
        target = self.tmp / 'surrogate-proj'
        before = list(self.tmp.iterdir())
        r2 = act.activate(str(target), {'name': 'Caf\udce9', 'project_type': 'web app'})
        self.assertEqual(r2['status'], 'invalid')
        self.assertEqual(r2['problems'][0]['problem'], 'must not contain unpaired surrogate characters')
        self.assertFalse(target.exists())
        self.assertEqual(list(self.tmp.iterdir()), before)

    # F4 ------------------------------------------------------------------------------------------
    def test_malformed_journal_entries_give_a_bounded_result(self):
        for files in ({'STATUS.md': ['a']}, {'STATUS.md': {'pending': ['x']}}, {'STATUS.md': {'written': 5}}):
            with self.subTest(files=files):
                shutil.rmtree(self.project, True)
                self.project.mkdir()
                path = self.project / act.JOURNAL
                path.write_text(json.dumps({'schema': act.SCHEMA, 'intake': {'name': 'X'}, 'files': files}))
                before = path.read_bytes()
                for args in (('resume', self.project), ('activate', self.project, '--name', 'X')):
                    code, r = self.cli_json(*args)
                    self.assertEqual((code, r['status']), (1, 'blocked'))
                    self.assertIn('malformed entry', r['errors'][0])
                self.assertEqual(path.read_bytes(), before)
                self.assertEqual([p.name for p in self.project.iterdir()], [act.JOURNAL])

    def test_overlong_path_component_is_invalid_input(self):
        code, r = self.cli_json('activate', self.tmp / ('x' * 300), '--name', 'Long')
        self.assertEqual((code, r['status']), (2, 'invalid'))
        self.assertIn('longer than 255 bytes', r['problems'][0]['problem'])
        code, r = self.cli_json('activate', self.tmp / '/'.join(['d' * 200] * 5), '--name', 'Deep')
        self.assertEqual((code, r['status']), (2, 'invalid'))

    @unittest.skipIf(os.name != 'posix' or (hasattr(os, 'geteuid') and os.geteuid() == 0), 'needs POSIX non-root')
    def test_read_only_root_gives_a_bounded_result(self):
        self.project.mkdir()
        os.chmod(self.project, 0o555)
        self.addCleanup(os.chmod, self.project, 0o755)
        code, r = self.cli_json('activate', self.project, '--name', 'RO')
        self.assertEqual((code, r['status']), (1, 'blocked'))
        self.assertIn('could not create', r['errors'][0])
        self.assertEqual(list(self.project.iterdir()), [])

    # F5 ------------------------------------------------------------------------------------------
    def test_leftover_temp_files_are_removed_but_nothing_else(self):
        self.activate(deploy_model='manual')
        hexid = 'ab12' * 4
        own = [f'.STATUS.md.{hexid}.activation-tmp', f'..solaris-activation.json.{hexid}.activation-tmp',
               f'Scope/.ROUND-PLAN.md.{hexid}.activation-tmp', f'Delivery/.CREDENTIALS.md.{hexid}.activation-tmp']
        for rel in own:
            (self.project / rel).write_text('half-written generated text')
        keep = {'Scope/.STATUS.md.%s.activation-tmp' % hexid: 'wrong folder for this target',
                '.notes.md.%s.activation-tmp' % hexid: 'not one of the tool targets',
                '.STATUS.md.123.activation-tmp': 'not the temp-name shape',
                'Development/.STATUS.md.%s.activation-tmp' % hexid: 'owner folder'}
        for rel, text in keep.items():
            (self.project / rel).write_text(text)
        link = self.project / f'Delivery/.CREDENTIALS.md.{"cd34" * 4}.activation-tmp'
        link.symlink_to(self.outside / 'sentinel')
        r = self.activate(deploy_model='manual')
        self.assertEqual(sorted(r['removed_temp_files']), sorted(own))
        for rel in own:
            self.assertFalse((self.project / rel).exists(), rel)
        for rel, text in keep.items():
            self.assertEqual((self.project / rel).read_text(), text)
        self.assertTrue(link.is_symlink())
        self.assert_outside_untouched()

    # F6 ------------------------------------------------------------------------------------------
    def test_empty_lock_is_reported_as_stale(self):
        self.activate(deploy_model='manual')
        (self.project / act.LOCK).write_bytes(b'')
        r = self.activate(resume=True)
        self.assertEqual(r['status'], 'blocked')
        self.assertIn('stale lock', r['errors'][0])
        self.assertIn('delete .solaris-activation.lock', r['errors'][0])

    # F7, F8 --------------------------------------------------------------------------------------
    def test_deploy_marker_only_in_the_deploy_field_and_commit_ids_in_briefs(self):
        for field in ('name', 'brief'):
            with self.subTest(field=field):
                _, problems = act.normalize_intake({'name': 'Acme', field: 'Acme DEPLOY-MODEL: main=live'})
                self.assertEqual(problems, [{'field': field, 'problem': 'must not contain a DEPLOY-MODEL: marker'}])
        _, problems = act.normalize_intake({'name': 'Acme', 'credentials': [
            {'system': 'ci', 'location': 'Vault deploy_model: main=live'}]})
        self.assertEqual(problems[0]['field'], 'credentials[1].location')
        sha1 = '41132041afeb2cce63a68554caf18cf6992a11ae'
        for brief in (f'fork of {sha1}', f'based on commit {sha1}', f'sha256 revision {"0f" * 32}'):
            with self.subTest(brief=brief):
                self.assertEqual(act.normalize_intake({'name': 'Acme', 'brief': brief})[1], [])
        for brief in (f'notes {sha1}', f'token {sha1}'):
            self.assertTrue(act.normalize_intake({'name': 'Acme', 'brief': brief})[1])  # no commit context: refused
        self.assertTrue(act.normalize_intake({'name': f'commit {sha1}'})[1])  # only briefs get the exemption

    # test gaps: no_intent_journal and no_lock mutants, crash during changed intake ---------------------
    def kill_beta_after(self, filename):
        p = subprocess.run([sys.executable, '-c', KILL_AFTER_WRITE, str(TOOL.parent), str(self.project), filename],
                           capture_output=True, text=True, env=dict({name: os.environ[name] for name in (
                                                                        'PATH', 'HOME', 'USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'TMPDIR',
                                                                        'TMP', 'TEMP', 'SystemRoot', 'SYSTEMROOT', 'SystemDrive', 'COMSPEC',
                                                                        'ComSpec', 'PATHEXT', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TZ',
                                                                        'PYTHONUTF8', 'PYTHONIOENCODING', 'PYTHONNOUSERSITE', 'PYTHONSAFEPATH', 'GIT_CONFIG_NOSYSTEM', 'GIT_CONFIG_GLOBAL',
                                                                        'GIT_CONFIG_SYSTEM', 'SSL_CERT_FILE', 'SSL_CERT_DIR', 'REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'CI',
                                                                        'GITHUB_ACTIONS',
                                                                    ) if name in os.environ}, PYTHONDONTWRITEBYTECODE='1'))
        self.assertEqual(p.returncode, -9, p.stderr)
        lock = self.project / act.LOCK
        self.assertTrue(lock.exists())
        r = self.activate(resume=True)
        self.assertEqual(r['status'], 'blocked')
        self.assertIn('stale lock', r['errors'][0])  # documented recovery: the owner deletes the stale lock
        lock.unlink()

    def test_crash_during_changed_intake_then_resume_converges_on_the_new_intake(self):
        self.activate(name='Alpha', deploy_model='staging-alpha')
        self.kill_beta_after('STATUS.md')
        self.assertIn('Beta', (self.project / 'STATUS.md').read_text())
        self.assertIn('Alpha', (self.project / 'Scope/ROUND-PLAN.md').read_text())
        journal = json.loads((self.project / act.JOURNAL).read_text())
        self.assertEqual(journal['intake']['name'], 'Beta')  # the intent was journaled before the first write
        r = self.activate(resume=True)
        self.assertEqual(r['status'], 'complete', r)
        for rel in act.GENERATED:
            text = (self.project / rel).read_text()
            self.assertIn('Beta', text, rel)
            self.assertNotIn('Alpha', text, rel)

    def test_crash_during_changed_intake_then_new_intake_is_not_mistaken_for_owner_content(self):
        self.activate(name='Alpha', deploy_model='staging-alpha')
        self.kill_beta_after('STATUS.md')
        r = self.activate(name='Gamma', deploy_model='prod-gamma')
        self.assertEqual(r['status'], 'complete', r['gaps'])
        self.assertEqual(r['artifacts']['STATUS.md'], 'updated')
        for rel in act.GENERATED:
            self.assertIn('Gamma', (self.project / rel).read_text(), rel)

    def test_a_second_activation_during_a_write_is_blocked_by_the_lock(self):
        self.activate(name='Alpha', deploy_model='manual')
        inner = []

        def contend(rel):
            if not inner:
                inner.append(act.activate(str(self.project), {'name': 'Intruder', 'deploy_model': 'main=live'}))
        r = self.activate(name='Beta', deploy_model='manual', _before_write=contend)
        self.assertEqual(r['status'], 'complete')
        self.assertEqual(inner[0]['status'], 'blocked')
        self.assertIn('pid %d' % os.getpid(), inner[0]['errors'][0])
        for rel in act.GENERATED:
            text = (self.project / rel).read_text()
            self.assertIn('Beta', text, rel)
            self.assertNotIn('Intruder', text, rel)
        self.assertFalse((self.project / act.LOCK).exists())


if __name__ == '__main__':
    unittest.main()
