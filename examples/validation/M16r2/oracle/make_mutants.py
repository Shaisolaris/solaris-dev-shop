"""M16 mutants of grounded_eval.py: exact single-occurrence edits (aborts if an anchor is not unique).
Usage: python make_mutants.py SOURCE OUT_DIR  -> OUT_DIR/<name>/grounded_eval.py"""
import sys
from pathlib import Path

MUTANTS = [
    ("fabricated_quote_accepted", 'n = text.count(c["quote"])', 'n = max(1, text.count(c["quote"]))'),
    ("numbers_not_checked", 'if a_nums - q_nums or cov < 0.6 or not a_terms:', 'if cov < 0.6 or not a_terms:'),
    ("coverage_not_checked", 'if a_nums - q_nums or cov < 0.6 or not a_terms:', 'if a_nums - q_nums or not a_terms:'),
    ("any_answer_on_unanswerable_ok", 'out["verdict"] = "correct_abstain" if abstain else "answered_unanswerable"', 'out["verdict"] = "correct_abstain"'),
    ("missed_answer_passes", 'out["verdict"] = "missed_answer"', 'out["verdict"] = "correct_abstain"'),
    ("wrong_source_off", 'if sd and not any(c["doc"] in sd for c in ok):', 'if False:'),
    ("facts_not_in_quote_ok", 'norm(f) not in norm(answer) or norm(f) not in norm(quoted)', 'norm(f) not in norm(answer)'),
    ("stale_reported_invalid", 'if recorded and recorded != doc["sha256"]:', 'if False:'),
    ("relocation_not_allowed", 'if n == 1:', 'if n == -1:'),
    ("baseline_label_trusted", 'verified = len(body) == len(qs) and all(', 'verified = True or all('),
    ("imported_called_verified", 'not executed or verified by this evaluator', 'executed and verified by this evaluator'),
    ("resume_redoes_all", 'todo = [q for q in qs if q["id"] not in done]', 'todo = list(qs)'),
    ("journal_header_unchecked", '_need(h.get(k) == header[k],', '_need(True or h.get(k) == header[k],'),
    ("fault_plan_ignored", 'if fault.get(q["id"], 0) >= attempt:', 'if False:'),
    ("failure_still_writes", '''        sys.stdout.write(f"tool step failed: {failed}\\n{len(done)}/{len(qs)} questions done; "''',
     '''        _write_atomic(out, b"{}\\n")\n        sys.stdout.write(f"tool step failed: {failed}\\n{len(done)}/{len(qs)} questions done; "'''),
    ("conflict_check_off", 'if need_num and any(quantities(idx.sents[g[2]][3]) != quantities(idx.sents[top[2]][3]) for g in rivals):', 'if False:'),
    ("identifiers_not_exact", 'if cov + 1e-9 < min_cov or not ids <= idx.toks[sid]:', 'if cov + 1e-9 < min_cov:'),
    ("min_coverage_ignored", 'if cov + 1e-9 < min_cov or not ids <= idx.toks[sid]:', 'if not ids <= idx.toks[sid]:'),
    ("torn_tail_parsed", 'lines = [l for l in lines[:-1]] if lines else []', 'lines = [l for l in lines if l]'),
    ("need_number_ignored", 'if need_num and not quantities(idx.sents[sid][3]):', 'if False:'),
    ("cite_corpus_sha", '"doc_sha256": corpus["docs"][name]["sha256"]}', '"doc_sha256": corpus["sha256"]}'),
    ("cite_offset_shift", 'return {"doc": name, "start": s, "end": e, "quote": frag,', 'return {"doc": name, "start": s + 1, "end": e + 1, "quote": frag,'),
    ("abstain_truthy", 'abstain = r.get("abstain") is True', 'abstain = bool(r.get("abstain"))'),
    ("invalid_input_writes", '_need(not jpath.exists(), f"journal: {jpath.name} exists; pass --resume or remove it")', 'pass'),
    ("overwrite_input_allowed", '_need(not (out.exists() and p.exists() and os.path.samefile(out, p)), f"{out.name}: would overwrite an input")', 'pass'),
    ("symlink_doc_followed", '_need(not stat.S_ISLNK(st.st_mode), f"{what}: {p.name} is a symlink; pass the real file")', 'pass'),
    ("order_dependent_output", 'for q in qs)\n    _write_atomic(out, body.encode("utf-8"))', 'for q in sorted(qs, key=lambda q: q["question"]))\n    _write_atomic(out, body.encode("utf-8"))'),
    ("missing_record_ignored", 'out.update(verdict="missing_record")', 'out.update(verdict="correct_abstain")'),
]


def main(src, out):
    s = Path(src).read_text()
    ok = 0
    for name, a, b in MUTANTS:
        n = s.count(a)
        if n != 1:
            print(f"ANCHOR {name}: found {n} times; mutant not made")
            continue
        d = Path(out) / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "grounded_eval.py").write_text(s.replace(a, b))
        ok += 1
        print(f"OK {name}")
    print(f"{ok}/{len(MUTANTS)} mutants made")
    return 0 if ok == len(MUTANTS) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
