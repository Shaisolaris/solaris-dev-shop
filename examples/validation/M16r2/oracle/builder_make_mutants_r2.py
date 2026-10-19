#!/usr/bin/env python3
"""G16 r2 mutants: the 28 M16 mutants (read from the M16 evidence, never edited; anchors the r2 edit moved are
re-pointed in MOVED with the same intent) plus r2 mutants, one per fix.
Usage: make_mutants_r2.py <grounded_eval.py> <out> <M16 make_mutants.py>"""
import importlib.util, sys
from pathlib import Path

MOVED = {
    "numbers_not_checked": [('if a_nums - q_nums or a_ids or cov < 0.6 or not a_terms:', 'if a_ids or cov < 0.6 or not a_terms:')],
    "coverage_not_checked": [('if a_nums - q_nums or a_ids or cov < 0.6 or not a_terms:', 'if a_nums - q_nums or a_ids or not a_terms:')],
    "facts_not_in_quote_ok": [('not has_phrase(f, answer) or not any(has_phrase(f, c["quote"]) for c in ok)', 'not has_phrase(f, answer)')],
    "conflict_check_off": [('if any(quantities(idx.sents[g[2]][3]) != top_q and (need_num or (top_q and quantities(idx.sents[g[2]][3]))) for g in rivals):', 'if False:')],
    "overwrite_input_allowed": [('        _need(not same, f"{out.name}: would overwrite an input")', '        pass')],
    "order_dependent_output": [('for q in qs)\n        _write_atomic(out, body.encode("utf-8"))',
                                'for q in sorted(qs, key=lambda q: q["question"]))\n        _write_atomic(out, body.encode("utf-8"))')],
    "failure_still_writes": [('            sys.stdout.write(f"tool step failed: {failed}\\n',
                              '            _write_atomic(out, b"{}\\n")\n            sys.stdout.write(f"tool step failed: {failed}\\n')],
    "stale_reported_invalid": [('if recorded and recorded != doc["sha256"] and other_snapshot:', 'if False:')],
}
R2 = {
    "r2_n1_no_negation": [('if negated(answer) != any(negated(x) for x in sents):', 'if False:')],
    "r2_n1_multi_sentence_ok": [('span = next(((s, e) for s, e in sentence_spans(text) if s <= s0 and e0 <= e), None)', 'span = (s0, e0)')],
    "r2_n1_no_subject_binding": [('if (actx & sterms) - qc:\n                    continue', 'if False:\n                    continue')],
    "r2_n2_no_unit_check": [('if anext is not None and anext not in STOP and qnext is not None and _stem(anext) != _stem(qnext):', 'if False:')],
    "r2_n2_fact_substring": [('return f" {norm(phrase)} " in f" {norm(text)} "', 'return norm(phrase) in norm(text)')],
    "r2_n2_ids_unchecked": [('a_ids = idents(answer) - idents(quoted)', 'a_ids = set()')],
    "r2_n2_numbers_in_identifiers": [('return {t.replace(",", "") for t in TOK_RE.findall(text.lower()) if NUM_RE.fullmatch(t)}',
                                      'return {n.replace(",", "") for n in NUM_RE.findall(text)}')],
    "r2_n3_need_num_only": [('and (need_num or (top_q and quantities(idx.sents[g[2]][3])))', 'and need_num')],
    "r2_n4_no_near_miss": [('        if near_miss(sid):\n            continue', '        if False:\n            continue')],
    "r2_n5_snapshot_folder_allowed": [('_need(c != out and c not in out.parents,', '_need(True,')],
    "r2_n6_abstain_claim_ok": [('if abstain and asserted:', 'if False:')],
    "r2_n7_stale_without_meta": [('other = bool(meta) and isinstance(meta.get("corpus_sha256"), str) and meta.get("corpus_sha256") != corpus["sha256"]', 'other = True')],
    "r2_n8_no_chain_check": [('_need(r.get("chain") == _chain(prev, r),', '_need(True,')],
    "r2_n8_no_lock": [('        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)', '        pass')],
    "r2_n9_fault_values_unchecked": [('_need(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= MAX_FAULTS,', '_need(True,')],
    "r2_n9_out_equals_journal": [('_need(jpath != out, ', '_need(True, ')],
    "r2_n10_claims_echoed": [('"provenance": {"producer": _claimed(producer),', '"provenance": {"producer": producer,')],
    "r2_n11_instructions_used": [('                if INSTRUCTION_RE.search(frag):', '                if False:')],
}


def main(src, out, m16):
    spec = importlib.util.spec_from_file_location("m16mut", m16)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    allm = {name: [(a, b)] for name, a, b in mod.MUTANTS}
    allm.update(MOVED)
    allm.update(R2)
    text = Path(src).read_text()
    for name, reps in allm.items():
        t = text
        for old, new in reps:
            n = t.count(old)
            if n != 1:
                raise SystemExit(f"{name}: pattern found {n} times: {old[:70]!r}")
            t = t.replace(old, new)
        compile(t, name, "exec")
        d = Path(out) / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "grounded_eval.py").write_text(t)
        print(name)


if __name__ == "__main__":
    main(*sys.argv[1:4])
