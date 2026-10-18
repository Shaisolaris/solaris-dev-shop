"""G16: offline grounded-answer evals (employees/engineering/llm-agent-designer/grounded_eval.py).

Real files, real subprocesses, no network and no model. The Harbor Line snapshot under
examples/capabilities/G16/fixtures is fictional; its expected verdicts are worked out by hand
in examples/capabilities/G16/README.md.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / 'employees' / 'engineering' / 'llm-agent-designer' / 'grounded_eval.py'
G16 = ROOT / 'examples' / 'capabilities' / 'G16'
FIX = G16 / 'fixtures'
V1, V2 = FIX / 'snapshot-v1', FIX / 'snapshot-v2'
Q1, Q2 = FIX / 'questions-v1.jsonl', FIX / 'questions-v2.jsonl'
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
ANSWERABLE = ['q01', 'q02', 'q03', 'q04', 'q05', 'q06', 'q07', 'q08']
UNANSWERABLE = ['q09', 'q10', 'q11', 'q12']


def cli(*args, env=ENV):
    p = subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True, env=env, timeout=600)
    return p.returncode, p.stdout, p.stderr


def lines(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix='g16-test-')
        self.tmp = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()

    def answer(self, corpus=V1, questions=Q1, out='a.jsonl', *extra):
        code, stdout, err = cli('answer', '--corpus', corpus, '--questions', questions, '--out', self.tmp / out, *extra)
        self.assertNotIn('Traceback', err)
        return code, stdout

    def evaluate(self, answers, corpus=V1, questions=Q1):
        code, stdout, err = cli('evaluate', '--corpus', corpus, '--questions', questions, '--answers', answers, '--json')
        self.assertNotIn('Traceback', err)
        return code, json.loads(stdout)

    def verdicts(self, rep):
        return {r['id']: r['verdict'] for r in rep['results']}


class Baseline(Base):
    def test_answers_are_exact_spans_and_unanswerable_questions_abstain(self):
        code, out = self.answer()
        self.assertEqual((code, out.strip()), (0, 'answered 8, abstained 4 of 12'))
        meta, *recs = lines(self.tmp / 'a.jsonl')
        self.assertEqual(meta['producer']['kind'], 'deterministic_baseline')
        by = {r['id']: r for r in recs}
        self.assertEqual([q for q in by if not by[q]['abstain']], ANSWERABLE)
        for qid in ANSWERABLE:
            for c in by[qid]['citations']:
                text = (V1 / c['doc']).read_text(encoding='utf-8')
                self.assertEqual(text[c['start']:c['end']], c['quote'], qid)
        self.assertEqual(by['q01']['answer'], 'A single adult ride costs 2.75 dollars on any bus or ferry.')
        self.assertEqual(by['q04']['citations'][0]['doc'], 'refunds.md')
        self.assertIn('10 business days', by['q04']['answer'])
        for qid in UNANSWERABLE:
            self.assertEqual((by[qid]['answer'], by[qid]['citations']), ('', []), qid)

    def test_evaluator_passes_the_baseline_and_says_what_it_is(self):
        self.answer()
        code, rep = self.evaluate(self.tmp / 'a.jsonl')
        self.assertEqual((code, rep['status'], rep['metrics']['passed']), (0, 'pass', 12))
        self.assertEqual(rep['counts']['correct_supported'], 8)
        self.assertEqual(rep['counts']['correct_abstain'], 4)
        self.assertEqual(rep['metrics']['citation_validity'], '8/8')
        self.assertIs(rep['provenance']['baseline_reproduced'], True)
        self.assertIn('re-run here and matched', rep['provenance']['evidence'])
        self.assertIn('no model', rep['provenance']['evaluator'])

    def test_rerun_and_four_workers_are_byte_identical(self):
        self.answer(V1, Q1, 'a.jsonl')
        self.answer(V1, Q1, 'b.jsonl', '--workers', '4')
        self.assertEqual((self.tmp / 'a.jsonl').read_bytes(), (self.tmp / 'b.jsonl').read_bytes())


class Grading(Base):
    def baseline(self):
        self.answer()
        meta, *recs = lines(self.tmp / 'a.jsonl')
        return meta, {r['id']: r for r in recs}

    def write(self, meta, by, name='t.jsonl'):
        p = self.tmp / name
        p.write_text(''.join(json.dumps(r) + '\n' for r in ([meta] if meta else []) + [by[k] for k in sorted(by)]))
        return p

    def test_imported_example_is_graded_by_hand_checked_verdicts(self):
        code, rep = self.evaluate(FIX / 'answers-imported-example.jsonl')
        self.assertEqual(code, 1)
        self.assertEqual(rep['metrics']['passed'], 7)
        got = {k: v for k, v in self.verdicts(rep).items() if v not in ('correct_supported', 'correct_abstain')}
        self.assertEqual(got, {'q02': 'unsupported_claim', 'q03': 'invalid_citation', 'q04': 'missed_answer',
                               'q07': 'uncited', 'q09': 'answered_unanswerable'})
        q02 = next(r for r in rep['results'] if r['id'] == 'q02')
        self.assertEqual(q02['support']['numbers_not_in_quotes'], ['1.50'])
        self.assertIn('not executed or verified', rep['provenance']['evidence'])
        self.assertIsNone(rep['provenance']['baseline_reproduced'])

    def test_each_defect_gets_its_own_verdict(self):
        meta, by = self.baseline()
        q05 = json.loads(json.dumps(by['q05']))
        by['q01']['citations'][0]['quote'] = by['q01']['citations'][0]['quote'].replace('2.75', '2.95')
        by['q02']['answer'] = by['q02']['answer'].replace('1.35', '1.25')
        by['q04']['citations'] = []
        by['q05'] = {'id': 'q05', 'abstain': True, 'answer': '', 'citations': []}
        by['q09'] = dict(by['q01'], id='q09', citations=by['q06']['citations'], answer=by['q06']['answer'])
        c = dict(by['q06']['citations'][0])
        by['q08']['citations'] = [c]
        by['q08']['answer'] = c['quote']
        del by['q12']
        by['q06'] = dict(q05, id='q06')  # exact quote from the right document, but not the asked fact
        code, rep = self.evaluate(self.write(dict(meta, producer={'kind': 'external_model'}), by))
        v = self.verdicts(rep)
        self.assertEqual(code, 1)
        self.assertEqual({k: v[k] for k in ('q01', 'q02', 'q04', 'q05', 'q08', 'q09', 'q12')},
                         {'q01': 'invalid_citation', 'q02': 'unsupported_claim', 'q04': 'uncited',
                          'q05': 'missed_answer', 'q08': 'wrong_source', 'q09': 'answered_unanswerable',
                          'q12': 'missing_record'})
        self.assertEqual(v['q06'], 'incorrect')
        self.assertEqual(next(r for r in rep['results'] if r['id'] == 'q06')['missing_facts'], ['may ride'])
        self.assertEqual(v['q03'], 'correct_supported')

    def test_unlabelled_and_forged_baseline_files_are_not_called_deterministic(self):
        meta, by = self.baseline()
        _, rep = self.evaluate(self.write(None, by, 'unlabelled.jsonl'))
        self.assertEqual(rep['status'], 'pass')
        self.assertIn('unlabelled', rep['provenance']['evidence'])
        by['q06']['answer'] += ' Staff confirmed this.'
        _, rep = self.evaluate(self.write(meta, by, 'forged.jsonl'))
        self.assertIs(rep['provenance']['baseline_reproduced'], False)
        self.assertIn('unverified', rep['provenance']['evidence'])
        self.assertNotIn('re-run here and matched', rep['provenance']['evidence'])


class Conflicts(Base):
    def test_sources_that_disagree_on_a_number_make_the_baseline_abstain(self):
        snap = self.tmp / 'snap'
        snap.mkdir()
        (snap / 'a.md').write_text('# Passes\nA day pass costs 5 dollars on every route.\n')
        (snap / 'b.md').write_text('# Passes\nA day pass costs 6 dollars on every route.\n')
        (snap / 'c.md').write_text('# Bikes\nBikes ride free on every route.\n')
        q = self.tmp / 'q.jsonl'
        q.write_text(json.dumps({'id': 'c1', 'question': 'How much does a day pass cost?',
                                 'expect': {'answerable': False}}) + '\n'
                     + json.dumps({'id': 'c2', 'question': 'Do bikes ride free?',
                                   'expect': {'answerable': True, 'facts': ['ride free'], 'support_docs': ['c.md']}}) + '\n')
        self.assertEqual(self.answer(snap, q)[0], 0)
        by = {r['id']: r for r in lines(self.tmp / 'a.jsonl')[1:]}
        self.assertEqual((by['c1']['abstain'], by['c1']['reason']), (True, 'conflicting_sources'))
        self.assertEqual(sorted(c['doc'] for c in by['c1']['citations']), ['a.md', 'b.md'])
        self.assertFalse(by['c2']['abstain'])
        code, rep = self.evaluate(self.tmp / 'a.jsonl', snap, q)
        self.assertEqual((code, self.verdicts(rep)), (0, {'c1': 'correct_abstain', 'c2': 'correct_supported'}))


class WhenQuestions(Base):
    def test_calendar_words_answer_when_questions_and_modal_may_does_not(self):
        snap = self.tmp / 'snap'
        snap.mkdir()
        (snap / 'hours.md').write_text('# Hours\nThe Quay branch is closed on Mondays.\nThe pool reopens on 3 May.\n'
                                       'Service animals may ride on all buses.\n')
        q = self.tmp / 'q.jsonl'
        q.write_text(''.join(json.dumps(x) + '\n' for x in [
            {'id': 'w1', 'question': 'When is the Quay branch closed?',
             'expect': {'answerable': True, 'facts': ['Mondays'], 'support_docs': ['hours.md']}},
            {'id': 'w2', 'question': 'When does the pool reopen?',
             'expect': {'answerable': True, 'facts': ['3 May'], 'support_docs': ['hours.md']}},
            {'id': 'w3', 'question': 'When can service animals ride?', 'expect': {'answerable': False}},
            {'id': 'w4', 'question': 'How many days is the Quay branch closed?', 'expect': {'answerable': False}}]))
        self.assertEqual(self.answer(snap, q)[0], 0)
        code, rep = self.evaluate(self.tmp / 'a.jsonl', snap, q)
        self.assertEqual(self.verdicts(rep), {'w1': 'correct_supported', 'w2': 'correct_supported',
                                              'w3': 'correct_abstain', 'w4': 'correct_abstain'})
        self.assertEqual(code, 0)


class SourceChange(Base):
    def test_changed_sources_are_named_and_reanswering_passes(self):
        self.answer()
        code, rep = self.evaluate(self.tmp / 'a.jsonl', V2, Q2)
        self.assertEqual(code, 1)
        v = self.verdicts(rep)
        self.assertEqual({k for k, x in v.items() if x == 'stale_citation'}, {'q03', 'q07'})
        status = {r['id']: r['citations'][0]['status'] for r in rep['results'] if r.get('citations')}
        self.assertEqual({k for k, s in status.items() if s == 'relocated'}, {'q01', 'q02', 'q08'})
        self.assertIn('answers were produced against a different snapshot; changed sources are reported per citation',
                      rep['notes'])
        self.assertIs(rep['provenance']['baseline_reproduced'], False)
        self.answer(V2, Q2, 'b.jsonl')
        code, rep = self.evaluate(self.tmp / 'b.jsonl', V2, Q2)
        self.assertEqual((code, rep['metrics']['passed']), (0, 12))
        by = {r['id']: r for r in lines(self.tmp / 'b.jsonl')[1:]}
        self.assertIn('45 days', by['q03']['answer'])
        self.assertEqual(by['q07']['citations'][0]['doc'], 'paratransit.md')

    def test_deleted_document_makes_the_citation_stale(self):
        self.answer()
        snap = self.tmp / 'snap'
        shutil.copytree(V1, snap)
        (snap / 'refunds.md').unlink()
        _, rep = self.evaluate(self.tmp / 'a.jsonl', snap, Q1)
        q04 = next(r for r in rep['results'] if r['id'] == 'q04')
        self.assertEqual(q04['verdict'], 'stale_citation')
        self.assertIn('no longer in the snapshot', q04['citations'][0]['detail'])


class FaultAndResume(Base):
    def test_failed_tool_step_stops_and_resume_completes_identically(self):
        self.answer(V1, Q1, 'clean.jsonl')
        j = self.tmp / 'j.jsonl'
        args = ('--journal', j, '--fault-plan', FIX / 'fault-plan.json')
        code, out = self.answer(V1, Q1, 'a.jsonl', *args)
        self.assertEqual(code, 3)
        self.assertIn('retrieval tool failed for q05', out)
        self.assertFalse((self.tmp / 'a.jsonl').exists())
        entries = lines(j)
        self.assertEqual([e['id'] for e in entries[1:] if e['kind'] == 'failed'], ['q05'])
        self.assertEqual(len([e for e in entries[1:] if e['kind'] == 'done']), 11)
        code, out = self.answer(V1, Q1, 'a.jsonl', *args, '--resume')
        self.assertEqual(code, 0)
        self.assertIn('resumed with 11 from the journal', out)
        self.assertEqual((self.tmp / 'a.jsonl').read_bytes(), (self.tmp / 'clean.jsonl').read_bytes())
        self.assertEqual(sum(1 for e in lines(j) if e.get('kind') == 'done' and e['id'] != 'q05'), 11)  # no step redone

    def test_unsafe_resume_is_refused_and_a_torn_tail_is_dropped(self):
        j = self.tmp / 'j.jsonl'
        self.answer(V1, Q1, 'a.jsonl', '--journal', j, '--fault-plan', FIX / 'fault-plan.json')
        good = j.read_bytes()
        code, out = self.answer(V2, Q1, 'a.jsonl', '--journal', j, '--resume')
        self.assertEqual(code, 2)
        self.assertIn('corpus_sha256 differs', out)
        self.assertEqual(j.read_bytes(), good)
        rows = good.split(b'\n')
        j.write_bytes(b'\n'.join(rows[:3] + [b'{not json'] + rows[3:]))
        code, out = self.answer(V1, Q1, 'a.jsonl', '--journal', j, '--resume')
        self.assertEqual(code, 2)
        self.assertIn('corrupted', out)
        j.write_bytes(good + b'{"id": "q05", "kind": "do')
        code, out = self.answer(V1, Q1, 'a.jsonl', '--journal', j, '--resume', '--fault-plan', FIX / 'fault-plan.json')
        self.assertEqual(code, 0)
        self.assertIn('dropped 1 torn journal line', out)


class InvalidInput(Base):
    def test_invalid_inputs_exit_2_and_write_nothing(self):
        report = self.tmp / 'r.json'
        report.write_text('previous report')
        bad = self.tmp / 'bad.jsonl'
        dup = self.tmp / 'dup.jsonl'
        dup.write_text(Q1.read_text().splitlines()[0] + '\n' + Q1.read_text().splitlines()[0] + '\n')
        for text in ('{"id": "q01"', '{"id": "q01", "id": "q02", "question": "x", "expect": {"answerable": false}}'):
            bad.write_text(text + '\n')
            code, out, _ = cli('evaluate', '--corpus', V1, '--questions', bad, '--answers', FIX / 'answers-imported-example.jsonl',
                               '--out', report)
            self.assertEqual(code, 2, text)
            self.assertIn('nothing written', out)
        code, out, _ = cli('answer', '--corpus', V1, '--questions', dup, '--out', self.tmp / 'x.jsonl')
        self.assertEqual(code, 2)
        self.assertFalse((self.tmp / 'x.jsonl').exists())
        self.assertEqual(report.read_text(), 'previous report')

    def test_outputs_never_overwrite_inputs_or_follow_links(self):
        snap = self.tmp / 'snap'
        shutil.copytree(V1, snap)
        before = (snap / 'fares.md').read_bytes()
        code, _, _ = cli('answer', '--corpus', snap, '--questions', Q1, '--out', snap / 'fares.md')
        self.assertEqual(code, 2)
        self.assertEqual((snap / 'fares.md').read_bytes(), before)
        (snap / 'linked.md').symlink_to(self.tmp / 'elsewhere.md')
        code, out, _ = cli('answer', '--corpus', snap, '--questions', Q1, '--out', self.tmp / 'a.jsonl')
        self.assertEqual(code, 2)
        self.assertFalse((self.tmp / 'a.jsonl').exists())


class Offline(Base):
    def test_runs_with_sockets_denied(self):
        guard = self.tmp / 'guard'
        guard.mkdir()
        (guard / 'sitecustomize.py').write_text(
            'import socket\n'
            'def _deny(*a, **k):\n    raise RuntimeError("network denied in G16 test")\n'
            'socket.socket = _deny\nsocket.create_connection = _deny\n')
        env = dict(ENV, PYTHONPATH=str(guard))
        code, _, err = cli('answer', '--corpus', V1, '--questions', Q1, '--out', self.tmp / 'a.jsonl', env=env)
        self.assertEqual(code, 0, err)
        code, out, err = cli('evaluate', '--corpus', V1, '--questions', Q1, '--answers', self.tmp / 'a.jsonl', env=env)
        self.assertEqual(code, 0, err)


class Oracle(Base):
    def oracle(self, tool):
        p = subprocess.run([sys.executable, str(G16 / 'grounding_oracle.py'), '--tool', f'{sys.executable} {tool}',
                            '--scale-docs', '300', '--json'], capture_output=True, text=True, env=ENV, timeout=900)
        return p.returncode, json.loads(p.stdout)

    def test_oracle_accepts_the_tool_and_rejects_both_stubs(self):
        code, rep = self.oracle(TOOL)
        self.assertEqual((code, rep['passed'], rep['total']), (0, 11, 11))
        for stub, most in (('noop_stub.py', 0), ('naive_stub.py', 1)):
            code, rep = self.oracle(G16 / stub)
            self.assertNotEqual(code, 0, stub)
            self.assertLessEqual(rep['passed'], most, stub)


if __name__ == '__main__':
    unittest.main()
