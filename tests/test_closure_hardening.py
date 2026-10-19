"""Finding closure and waiver hardening.

A legitimate independent verification closes a blocking finding. The accountable
role cannot self-approve it, a waiver must be active, unexpired, human-authorised
and not self-approved, and empty or malformed evidence cannot stand in for
independent verification. Evidence strings are declared text only: nothing they
name is opened or executed. Time is fixed for determinism.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / 'employees/quality-security/assurance/quality_os.py'
sys.path.insert(0, str(ENGINE.parent))
import quality_os as q

AS_OF = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)
VERIFIED = ['code-reviewer re-ran the XSS payload suite against the fix revision; payload escaped']


def finding(**over):
    f = q.create_finding(defect_kind='security', severity='S1', title='Stored XSS in profile',
                         evidence=['scan: payload reflected in profile name'],
                         reporter_role='qa-engineer', finding_id='fnd-hard-1')
    for key, value in over.items():
        setattr(f, key, value)
    return f


def waiver(**over):
    data = dict(waiver_id='wvr-hard-1', finding_id='fnd-hard-1',
                requested_by_role='security-auditor', approved_by_role='human-owner',
                human_authority=True, justification='Accepted risk until the patch release',
                expires_at='2026-12-01T00:00:00+00:00', status='active')
    data.update(over)
    return q.Waiver(**data)


class LegitimateClosure(unittest.TestCase):
    def test_independent_verifier_closes_blocking_finding(self):
        closed, codes = q.close_finding(finding(), closer_role='code-reviewer',
                                        independent_evidence=VERIFIED, as_of=AS_OF)
        self.assertEqual(codes, [])
        self.assertEqual(closed.status, 'closed')
        self.assertEqual(closed.closed_by_role, 'code-reviewer')
        self.assertEqual(closed.evidence[-1], VERIFIED[0])

    def test_human_owner_with_evidence_closes(self):
        allowed, codes = q.can_close_finding(finding(), closer_role='human-owner',
                                             independent_evidence=VERIFIED, as_of=AS_OF)
        self.assertTrue(allowed, codes)

    def test_non_blocking_self_close_without_evidence_still_allowed(self):
        allowed, codes = q.can_close_finding(finding(severity='S3'), closer_role='security-auditor',
                                             independent_evidence=[], as_of=AS_OF)
        self.assertTrue(allowed, codes)

    def test_valid_active_waiver_closes_waived_finding(self):
        allowed, codes = q.can_close_finding(finding(status='waived'), closer_role='security-auditor',
                                             independent_evidence=[], waiver=waiver(), as_of=AS_OF)
        self.assertTrue(allowed, codes)

    def test_propose_waiver_valid(self):
        w, codes = q.propose_waiver(finding(), requested_by_role='security-auditor',
                                    approved_by_role='human-owner', human_authority=True,
                                    justification='Accepted risk until the patch release',
                                    expires_at='2026-12-01', as_of=AS_OF)
        self.assertEqual(codes, [])
        self.assertEqual(w.status, 'active')


class SelfApproval(unittest.TestCase):
    def test_accountable_self_close_rejected(self):
        closed, codes = q.close_finding(finding(), closer_role='security-auditor',
                                        independent_evidence=['I fixed it'], as_of=AS_OF)
        self.assertEqual(codes, ['SELF_APPROVAL_FORBIDDEN'])
        self.assertEqual(closed.status, 'open')

    def test_unknown_severity_is_not_treated_as_non_blocking(self):
        for sev in ('s1', 'critical', '', None):
            allowed, codes = q.can_close_finding(finding(severity=sev), closer_role='security-auditor',
                                                 independent_evidence=[], as_of=AS_OF)
            self.assertFalse(allowed, sev)
            self.assertIn('INVALID_FINDING', codes)

    def test_unknown_status_rejected(self):
        allowed, codes = q.can_close_finding(finding(status='resolved'), closer_role='code-reviewer',
                                             independent_evidence=VERIFIED, as_of=AS_OF)
        self.assertFalse(allowed)
        self.assertIn('INVALID_FINDING', codes)

    def test_blank_verifier_role_does_not_admit_blank_closer(self):
        allowed, codes = q.can_close_finding(finding(verifier_role=''), closer_role='',
                                             independent_evidence=['x'], as_of=AS_OF)
        self.assertFalse(allowed)
        self.assertIn('INVALID_CLOSER_ROLE', codes)

    def test_verifier_equal_to_accountable_is_not_independent(self):
        allowed, codes = q.can_close_finding(finding(verifier_role='code-reviewer',
                                                     accountable_role='code-reviewer'),
                                             closer_role='code-reviewer',
                                             independent_evidence=VERIFIED, as_of=AS_OF)
        self.assertFalse(allowed)
        self.assertIn('SELF_APPROVAL_FORBIDDEN', codes)


class Waivers(unittest.TestCase):
    def blocked(self, w, code, f=None):
        allowed, codes = q.can_close_finding(f or finding(status='waived'),
                                             closer_role='security-auditor',
                                             independent_evidence=[], waiver=w, as_of=AS_OF)
        self.assertFalse(allowed, codes)
        self.assertIn(code, codes)

    def test_expired_waiver_rejected(self):
        self.blocked(waiver(expires_at='2026-10-01T00:00:00Z'), 'WAIVER_EXPIRED')

    def test_waiver_expiring_exactly_now_rejected(self):
        self.blocked(waiver(expires_at=AS_OF.isoformat()), 'WAIVER_EXPIRED')

    def test_unparseable_or_missing_expiry_rejected(self):
        for value in ('whenever', '', None, 20991231):
            self.blocked(waiver(expires_at=value), 'WAIVER_EXPIRY_INVALID')

    def test_self_approved_waiver_rejected(self):
        self.blocked(waiver(approved_by_role='security-auditor'), 'WAIVER_SELF_APPROVAL_FORBIDDEN')
        self.blocked(waiver(requested_by_role='code-reviewer', approved_by_role='code-reviewer'),
                     'WAIVER_SELF_APPROVAL_FORBIDDEN')

    def test_waiver_without_strict_human_authority_rejected(self):
        for value in (False, 'yes', 1, None):
            self.blocked(waiver(human_authority=value), 'HUMAN_AUTHORITY_REQUIRED')

    def test_waiver_short_justification_rejected(self):
        self.blocked(waiver(justification='ok'), 'WAIVER_JUSTIFICATION_REQUIRED')

    def test_waiver_for_other_finding_or_inactive_rejected(self):
        self.blocked(waiver(finding_id='fnd-other'), 'WAIVER_FINDING_MISMATCH')
        self.blocked(waiver(status='proposed'), 'WAIVER_NOT_ACTIVE')

    def test_non_waiver_object_rejected(self):
        self.blocked({'status': 'active', 'finding_id': 'fnd-hard-1'}, 'INVALID_WAIVER')

    def test_propose_waiver_rejects_past_or_invalid_expiry_and_loose_authority(self):
        base = dict(requested_by_role='security-auditor', approved_by_role='human-owner',
                    human_authority=True, justification='Accepted risk until the patch release',
                    expires_at='2026-12-01', as_of=AS_OF)
        cases = [({'expires_at': '2020-01-01'}, 'WAIVER_EXPIRED'),
                 ({'expires_at': 'not-a-date'}, 'WAIVER_EXPIRY_INVALID'),
                 ({'expires_at': ''}, 'WAIVER_EXPIRY_REQUIRED'),
                 ({'human_authority': 'no'}, 'HUMAN_AUTHORITY_REQUIRED'),
                 ({'requested_by_role': 'code-reviewer', 'approved_by_role': 'code-reviewer'},
                  'WAIVER_SELF_APPROVAL_FORBIDDEN')]
        for over, code in cases:
            w, codes = q.propose_waiver(finding(), **dict(base, **over))
            self.assertIsNone(w, over)
            self.assertIn(code, codes, over)


class Evidence(unittest.TestCase):
    def rejected(self, evidence, code):
        closed, codes = q.close_finding(finding(), closer_role='code-reviewer',
                                        independent_evidence=evidence, as_of=AS_OF)
        self.assertIn(code, codes, evidence)
        self.assertEqual(closed.status, 'open')

    def test_empty_evidence_rejected(self):
        self.rejected([], 'MISSING_CLOSURE_EVIDENCE')

    def test_blank_or_malformed_evidence_rejected(self):
        for value in (['', '   '], 'ok', {'verified': False}, [None], [1], None, ('ok', '')):
            self.rejected(value, 'INVALID_CLOSURE_EVIDENCE')

    def test_resubmitted_reporter_evidence_is_not_independent(self):
        self.rejected(['scan: payload reflected in profile name'], 'NON_INDEPENDENT_CLOSURE_EVIDENCE')

    def test_evidence_text_is_never_executed(self):
        marker = Path(tempfile.gettempdir()) / 'solaris-closure-hardening-marker'
        if marker.exists():
            marker.unlink()
        evidence = ['touch %s' % marker, 'https://example.invalid/verify', '$(touch %s)' % marker]
        allowed, codes = q.can_close_finding(finding(), closer_role='code-reviewer',
                                             independent_evidence=evidence, as_of=AS_OF)
        self.assertTrue(allowed, codes)
        self.assertFalse(marker.exists())


class Recovery(unittest.TestCase):
    def test_rejections_then_proper_close(self):
        f = finding()
        f1, c1 = q.close_finding(f, closer_role='security-auditor', independent_evidence=['done'],
                                 as_of=AS_OF)
        f2, c2 = q.close_finding(f1, closer_role='code-reviewer', independent_evidence=[' '],
                                 as_of=AS_OF)
        self.assertEqual((c1, f1.status), (['SELF_APPROVAL_FORBIDDEN'], 'open'))
        self.assertEqual((c2, f2.status), (['INVALID_CLOSURE_EVIDENCE'], 'open'))
        self.assertEqual(f2.evidence, f.evidence)
        f3, c3 = q.close_finding(f2, closer_role='code-reviewer', independent_evidence=VERIFIED,
                                 as_of=AS_OF)
        self.assertEqual((c3, f3.status), ([], 'closed'))
        _, c4 = q.close_finding(f3, closer_role='code-reviewer', independent_evidence=VERIFIED,
                                as_of=AS_OF)
        self.assertEqual(c4, ['ALREADY_CLOSED'])

    def test_expired_waiver_then_renewed_waiver(self):
        f = finding(status='waived')
        ok1, c1 = q.can_close_finding(f, closer_role='security-auditor', independent_evidence=[],
                                      waiver=waiver(expires_at='2026-01-01'), as_of=AS_OF)
        renewed, c2 = q.propose_waiver(finding(), requested_by_role='security-auditor',
                                       approved_by_role='human-owner', human_authority=True,
                                       justification='Renewed by owner for patch release',
                                       expires_at='2026-11-30T00:00:00Z', as_of=AS_OF)
        ok3, c3 = q.can_close_finding(f, closer_role='security-auditor', independent_evidence=[],
                                      waiver=renewed, as_of=AS_OF)
        self.assertEqual((ok1, c1), (False, ['WAIVER_EXPIRED']))
        self.assertEqual(c2, [])
        self.assertEqual((ok3, c3), (True, []))


class _CliHelpers:
    """Run a closure fixture through the real `run` command."""

    def run_fixture(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'closure.json'
            path.write_text(json.dumps(data), encoding='utf-8')
            proc = subprocess.run([sys.executable, str(ENGINE), 'run', str(path)],
                                  capture_output=True, text=True)
        self.assertNotIn('Traceback', proc.stderr)
        return proc.returncode, json.loads(proc.stdout)

    def fdict(self, **over):
        d = finding().to_dict()
        d.update(over)
        return d



class CliFixtures(_CliHelpers, unittest.TestCase):
    """The real `run` command: malformed closure fixtures block instead of crashing."""

    def test_legit_close_fixture_passes(self):
        code, out = self.run_fixture({'fixture_kind': 'closure', 'expect_blocked': False,
                                      'closer_role': 'code-reviewer',
                                      'independent_evidence': VERIFIED, 'finding': self.fdict()})
        self.assertEqual((code, out['ok'], out['evidence']['allowed']), (0, True, True))

    def test_expired_self_approved_waiver_fixture_is_blocked(self):
        w = waiver(approved_by_role='security-auditor', human_authority=False,
                   expires_at='2020-01-01T00:00:00Z').to_dict()
        code, out = self.run_fixture({'fixture_kind': 'closure', 'expect_blocked': True,
                                      'closer_role': 'security-auditor',
                                      'finding': self.fdict(status='waived'), 'waiver': w})
        self.assertEqual((code, out['ok'], out['evidence']['allowed']), (0, True, False))
        self.assertIn('WAIVER_EXPIRED', out['gate_codes'])

    def test_malformed_fixtures_return_invalid_packet(self):
        bad = [{'fixture_kind': 'closure'},
               {'fixture_kind': 'closure', 'finding': 'nope'},
               {'fixture_kind': 'closure', 'finding': self.fdict(extra='x')},
               {'fixture_kind': 'closure', 'finding': {'finding_id': 'f'}},
               {'fixture_kind': 'closure', 'finding': self.fdict(status='waived'),
                'waiver': {'waiver_id': 'w', 'note': 'extra'}},
               {'fixture_kind': 'closure', 'finding': self.fdict(), 'closer_role': 7}]
        for data in bad:
            code, out = self.run_fixture(data)
            self.assertEqual(code, 1, data)
            self.assertIn('INVALID_PACKET', out['gate_codes'], data)


MALFORMED_EVIDENCE = (None, 'ok', {'receipt': True}, [' '], [''], [None], ['ok', 3], b'ok')


class ReviewRound1WaivedInputs(unittest.TestCase):
    """Review round 1, defect 1: a valid waiver must not skip closer/evidence shape checks."""

    def test_malformed_evidence_rejected_with_valid_waiver(self):
        for ev in MALFORMED_EVIDENCE:
            f = finding(status='waived')
            allowed, codes = q.can_close_finding(f, closer_role='security-auditor',
                                                 independent_evidence=ev, waiver=waiver(), as_of=AS_OF)
            self.assertEqual((allowed, codes), (False, ['INVALID_CLOSURE_EVIDENCE']), ev)
            closed, codes = q.close_finding(f, closer_role='security-auditor',
                                            independent_evidence=ev, waiver=waiver(), as_of=AS_OF)
            self.assertEqual(codes, ['INVALID_CLOSURE_EVIDENCE'], ev)
            self.assertEqual((closed.status, closed.closed_by_role, closed.evidence),
                             ('waived', '', ['scan: payload reflected in profile name']), ev)
            self.assertEqual(f.evidence, ['scan: payload reflected in profile name'])

    def test_blank_or_nonstring_closer_rejected_with_valid_waiver(self):
        for closer in ('', '   ', None, ['security-auditor'], {}):
            f = finding(status='waived')
            allowed, codes = q.can_close_finding(f, closer_role=closer, independent_evidence=[],
                                                 waiver=waiver(), as_of=AS_OF)
            self.assertEqual((allowed, codes), (False, ['INVALID_CLOSER_ROLE']), closer)
            closed, codes = q.close_finding(f, closer_role=closer, independent_evidence=[],
                                            waiver=waiver(), as_of=AS_OF)
            self.assertEqual((codes, closed.status), (['INVALID_CLOSER_ROLE'], 'waived'), closer)

    def test_valid_waiver_closes_with_empty_sequence_by_accountable_closer(self):
        for ev in ([], ()):
            closed, codes = q.close_finding(finding(status='waived'), closer_role='security-auditor',
                                            independent_evidence=ev, waiver=waiver(), as_of=AS_OF)
            self.assertEqual((codes, closed.status, closed.closed_by_role),
                             ([], 'closed', 'security-auditor'))
            self.assertEqual(closed.evidence, ['scan: payload reflected in profile name'])

    def test_valid_waiver_closes_with_wellformed_receipt(self):
        closed, codes = q.close_finding(finding(status='waived'), closer_role='human-owner',
                                        independent_evidence=['owner waiver receipt wvr-hard-1'],
                                        waiver=waiver(), as_of=AS_OF)
        self.assertEqual((codes, closed.status), ([], 'closed'))
        self.assertEqual(closed.evidence[-1], 'owner waiver receipt wvr-hard-1')

    def test_rejected_waived_close_then_corrected_retry(self):
        f = finding(status='waived')
        f1, c1 = q.close_finding(f, closer_role='', independent_evidence='ok', waiver=waiver(),
                                 as_of=AS_OF)
        f2, c2 = q.close_finding(f1, closer_role='security-auditor', independent_evidence=None,
                                 waiver=waiver(), as_of=AS_OF)
        f3, c3 = q.close_finding(f2, closer_role='security-auditor', independent_evidence=[],
                                 waiver=waiver(), as_of=AS_OF)
        self.assertEqual((c1, c2, c3), (['INVALID_CLOSER_ROLE'], ['INVALID_CLOSURE_EVIDENCE'], []))
        self.assertEqual((f1.status, f2.status, f3.status), ('waived', 'waived', 'closed'))
        self.assertEqual(f2.evidence, f.evidence)

    def test_invalid_waiver_still_reported_for_wellformed_input(self):
        allowed, codes = q.can_close_finding(finding(status='waived'), closer_role='security-auditor',
                                             independent_evidence=[],
                                             waiver=waiver(expires_at='2026-01-01'), as_of=AS_OF)
        self.assertEqual((allowed, codes), (False, ['WAIVER_EXPIRED']))


class ReviewRound1Severity(unittest.TestCase):
    """Review round 1, defect 2: nonstring severity or status must not crash."""

    def test_nonstring_severity_rejected_by_api(self):
        for sev in ([], {}, ['S1'], {'S1': 1}, 1, None, 1.5, b'S1'):
            f = finding(severity=sev)
            allowed, codes = q.can_close_finding(f, closer_role='code-reviewer',
                                                 independent_evidence=['new receipt'], as_of=AS_OF)
            self.assertEqual((allowed, codes), (False, ['INVALID_FINDING']), sev)
            closed, codes = q.close_finding(f, closer_role='code-reviewer',
                                            independent_evidence=['new receipt'], as_of=AS_OF)
            self.assertEqual((codes, closed.status), (['INVALID_FINDING'], 'open'), sev)

    def test_nonstring_status_rejected_by_api(self):
        for status in ([], {}, None):
            allowed, codes = q.can_close_finding(finding(status=status), closer_role='code-reviewer',
                                                 independent_evidence=['new receipt'], as_of=AS_OF)
            self.assertEqual((allowed, codes), (False, ['INVALID_FINDING']), status)

    def test_known_severities_keep_behavior(self):
        for sev in ('S0', 'S1', 'S2'):
            ok, codes = q.can_close_finding(finding(severity=sev), closer_role='security-auditor',
                                            independent_evidence=VERIFIED, as_of=AS_OF)
            self.assertEqual((ok, codes), (False, ['SELF_APPROVAL_FORBIDDEN']), sev)
        for sev in ('S3', 'S4', 'info'):
            ok, codes = q.can_close_finding(finding(severity=sev), closer_role='security-auditor',
                                            independent_evidence=[], as_of=AS_OF)
            self.assertEqual((ok, codes), (True, []), sev)


class ReviewRound1Cli(_CliHelpers, unittest.TestCase):
    """The same probe cases through the real `run` command."""

    def test_nonstring_severity_fixture_is_invalid_packet(self):
        for sev in ([], {}, 1, None):
            code, out = self.run_fixture({'kind': 'closure', 'closer_role': 'code-reviewer',
                                          'independent_evidence': ['new receipt'],
                                          'finding': self.fdict(severity=sev)})
            self.assertEqual(code, 1, sev)
            self.assertIn('INVALID_PACKET', out['gate_codes'], sev)

    def test_waived_fixture_with_malformed_evidence_or_closer_is_blocked(self):
        w = waiver().to_dict()
        for closer, ev, want in (('security-auditor', 'ok', 'INVALID_CLOSURE_EVIDENCE'),
                                 ('security-auditor', None, 'INVALID_CLOSURE_EVIDENCE'),
                                 ('security-auditor', {'receipt': True}, 'INVALID_CLOSURE_EVIDENCE'),
                                 ('security-auditor', [' '], 'INVALID_CLOSURE_EVIDENCE'),
                                 ('', [], 'INVALID_CLOSER_ROLE')):
            code, out = self.run_fixture({'fixture_kind': 'closure', 'expect_blocked': True,
                                          'closer_role': closer, 'independent_evidence': ev,
                                          'finding': self.fdict(status='waived'), 'waiver': w})
            self.assertEqual((code, out['evidence']['allowed'], out['gate_codes']),
                             (0, False, [want]), (closer, ev))

    def test_valid_waiver_fixture_closes(self):
        code, out = self.run_fixture({'fixture_kind': 'closure', 'expect_blocked': False,
                                      'closer_role': 'security-auditor', 'independent_evidence': [],
                                      'finding': self.fdict(status='waived'),
                                      'waiver': waiver(expires_at='2099-01-01T00:00:00Z').to_dict()})
        self.assertEqual((code, out['ok'], out['evidence']['allowed']), (0, True, True))

class WaiverGovernedClosure(unittest.TestCase):
    """Root G05: waiver-closed findings stay current and are not reopened via reopen_finding."""

    def test_waiver_closure_is_current_and_not_reopened(self):
        f = finding(status='waived')
        w = waiver()
        closed, codes = q.close_finding(f, closer_role='release-manager', independent_evidence=[],
                                        waiver=w, as_of=AS_OF)
        self.assertEqual(codes, [])
        self.assertEqual(closed.status, 'closed')
        self.assertEqual(closed.waiver_id, w.waiver_id)
        self.assertEqual(closed.closed_at_revision, '')
        self.assertEqual(q.closure_is_current(closed, 'a' * 40), (True, []))
        self.assertEqual(q.closure_is_current(closed, 'b' * 40), (True, []))
        reopened, rcodes = q.reopen_finding(closed, reason='should not reopen waiver',
                                            current_revision='a' * 40, reopened_by_role='release-manager')
        self.assertEqual(rcodes, ['WAIVER_GOVERNS'])
        self.assertEqual(reopened.status, 'closed')
        # Non-waiver unbound closure still reports UNBOUND_CLOSURE
        bare = finding(status='open')
        closed2, c2 = q.close_finding(bare, closer_role='code-reviewer', independent_evidence=['verified ok'],
                                      subject_revision=None, verified_revision=None)
        # without subject, non-waived close may still work for non-blocking - use S2 carefully
        # Instead craft a closed finding without revision or waiver:
        unbound = finding(status='closed')
        unbound.closed_at_revision = ''
        unbound.waiver_id = ''
        self.assertEqual(q.closure_is_current(unbound, 'a' * 40), (False, ['UNBOUND_CLOSURE']))

if __name__ == '__main__':
    unittest.main()
