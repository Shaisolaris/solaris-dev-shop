#!/usr/bin/env python3
"""G16 oracle: does a candidate answer only from the snapshot, abstain when it must, grade honestly,
notice source changes and resume after a failed tool step?

The oracle writes a seeded synthetic spec-sheet corpus and KNOWS every fact and every sentence
offset before the candidate runs. Unanswerable questions are adversarial: the asked attribute is
stated for a sibling model (K7 vs K71) or the model does not exist. A candidate is any command with
    <cmd> answer   --corpus DIR --questions Q --out A [--journal J] [--resume] [--workers N] [--fault-plan F]
    <cmd> evaluate --corpus DIR --questions Q --answers A --json [--out R]
following the solaris.grounded-answers/1 and solaris.grounded-eval-report/1 formats. No network, no model.

Usage: grounding_oracle.py --tool "python3 path/to/grounded_eval.py" [--seed N] [--scale-docs N] [--json]
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import random
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

FAMS = ["Kestrel", "Heron", "Osprey", "Plover", "Merlin", "Avocet", "Godwit", "Dunlin"]
ATTRS = [("maximum flow", "litres per minute"), ("dry weight", "kilograms"), ("warranty period", "months"),
         ("rated voltage", "volts"), ("noise level", "decibels")]


class World:
    def __init__(self, seed, n_ent):
        rnd = random.Random(seed)
        self.rnd = rnd
        ents, used = [], set()
        while len(ents) < n_ent:
            fam, num = rnd.choice(FAMS), rnd.randrange(2, 400)
            if (fam, num) in used:
                continue
            used.add((fam, num))
            ents.append((fam, num))
            if rnd.random() < 0.3 and len(ents) < n_ent and (fam, num * 10 + 1) not in used:   # sibling trap
                used.add((fam, num * 10 + 1))
                ents.append((fam, num * 10 + 1))
        self.used = used
        self.docs = {}      # name -> list of (attr_index, value, unit) in order
        self.names = {}
        for fam, num in ents:
            name = f"{fam} K{num}"
            k = rnd.randint(2, 4)
            attrs = sorted(rnd.sample(range(len(ATTRS)), k))
            rows = []
            for ai in attrs:
                v = rnd.randrange(10, 900) if rnd.random() < 0.7 else f"{rnd.randrange(1, 99)}.{rnd.randrange(1, 9)}"
                rows.append([ai, str(v)])
            fn = f"{fam.lower()}-k{num}.md"
            self.docs[fn] = {"name": name, "rows": rows, "preamble": []}
            self.names[fn] = name

    @staticmethod
    def sentence(name, ai, v):
        a, u = ATTRS[ai]
        return f"The {name} has a {a} of {v} {u}."

    def text(self, fn):
        d = self.docs[fn]
        lines = [f"# {d['name']}"] + d["preamble"] + [self.sentence(d["name"], ai, v) for ai, v in d["rows"]]
        return "\n".join(lines) + "\n"

    def write(self, folder):
        folder = Path(folder)
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True)
        for fn in sorted(self.docs):
            (folder / fn).write_text(self.text(fn), encoding="utf-8")
        return folder

    def span(self, fn, ai):
        d = self.docs[fn]
        t = self.text(fn)
        for a, v in d["rows"]:
            if a == ai:
                s = self.sentence(d["name"], a, v)
                st = t.index(s)
                return {"doc": fn, "start": st, "end": st + len(s), "quote": s}, v
        return None, None

    def questions(self, n, seed):
        rnd = random.Random(seed)
        qs = []
        fns = sorted(self.docs)
        for i in range(n):
            fn = rnd.choice(fns)
            d = self.docs[fn]
            kind = rnd.random()
            have = {a for a, _ in d["rows"]}
            if kind < 0.65:
                ai = rnd.choice(sorted(have))
                a, u = ATTRS[ai]
                v = [x for x in d["rows"] if x[0] == ai][0][1]
                qs.append({"id": f"q{i:05d}", "question": f"What is the {a} of the {d['name']}?",
                           "expect": {"answerable": True, "facts": [f"{v} {u}"], "support_docs": [fn]}, "_doc": fn, "_ai": ai})
            elif kind < 0.85 and len(have) < len(ATTRS):
                ai = rnd.choice([x for x in range(len(ATTRS)) if x not in have])
                qs.append({"id": f"q{i:05d}", "question": f"What is the {ATTRS[ai][0]} of the {d['name']}?",
                           "expect": {"answerable": False}, "_doc": fn, "_ai": ai})
            else:
                fam = d["name"].split()[0]
                num = int(d["name"].split()[1][1:])
                ghost = num + 1000
                while (fam, ghost) in self.used:   # the ghost must really not exist (siblings are num*10+1)
                    ghost += 1000
                ai = rnd.randrange(len(ATTRS))
                qs.append({"id": f"q{i:05d}", "question": f"What is the {ATTRS[ai][0]} of the {fam} K{ghost}?",
                           "expect": {"answerable": False}, "_doc": None, "_ai": ai})
        return qs


def write_q(path, qs):
    Path(path).write_text("".join(json.dumps({k: v for k, v in q.items() if not k.startswith("_")}) + "\n" for q in qs), encoding="utf-8")


def run(tool, *args, timeout=900):
    t0 = time.monotonic()
    p = subprocess.run(shlex.split(tool) + [str(a) for a in args], capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, time.monotonic() - t0


def evaluate(tool, corpus, qpath, apath):
    code, out, _ = run(tool, "evaluate", "--corpus", corpus, "--questions", qpath, "--answers", apath, "--json")
    try:
        return code, json.loads(out)
    except ValueError:
        return code, None


def read_answers(path):
    lines = [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]
    meta = lines[0] if lines and lines[0].get("kind") == "meta" else None
    return meta, {r["id"]: r for r in (lines[1:] if meta else lines) if "id" in r}


def own_check(world_dir, qs, path):
    """Independent check of an answers file: quotes exact, answerable answered with the fact, unanswerable abstained."""
    errs = []
    if not Path(path).exists():
        return ["answers file missing"]
    meta, recs = read_answers(path)
    if not meta or not isinstance(meta.get("producer"), dict):
        errs.append("answers file has no producer metadata")
    for q in qs:
        r = recs.get(q["id"])
        if r is None:
            errs.append(f"{q['id']}: no record"); continue
        if not q["expect"]["answerable"]:
            if r.get("abstain") is not True:
                errs.append(f"{q['id']}: answered an unanswerable question: {r.get('answer', '')[:60]!r}")
            continue
        if r.get("abstain") is True:
            errs.append(f"{q['id']}: abstained on an answerable question"); continue
        fact = q["expect"]["facts"][0]
        if fact not in r.get("answer", ""):
            errs.append(f"{q['id']}: answer lacks {fact!r}")
        ok = False
        for c in r.get("citations") or []:
            p = Path(world_dir) / c.get("doc", "")
            if p.is_file():
                t = p.read_text(encoding="utf-8")
                if t[c.get("start", 0):c.get("end", 0)] == c.get("quote") and fact in c.get("quote", ""):
                    ok = True
        if not ok:
            errs.append(f"{q['id']}: no citation quotes the snapshot span holding the fact")
    return errs


def verdicts(rep):
    return {r["id"]: r["verdict"] for r in (rep or {}).get("results", [])}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--tool", required=True)
    ap.add_argument("--seed", type=int, default=1607)
    ap.add_argument("--docs", type=int, default=120)
    ap.add_argument("--scale-docs", type=int, default=3000)
    ap.add_argument("--scale-seconds", type=float, default=180.0)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    results, info = [], {}

    def check(cid, title, fn):
        try:
            errs = fn()
        except Exception as exc:
            errs = [f"oracle error: {exc.__class__.__name__}: {exc}"]
        results.append({"id": cid, "title": title, "pass": not errs, "errors": errs[:6]})

    with tempfile.TemporaryDirectory(prefix="g16-oracle-") as tmp:
        tmp = Path(tmp)
        w = World(a.seed, a.docs)
        c1 = w.write(tmp / "v1")
        qs = w.questions(300, a.seed + 1)
        q1 = tmp / "q1.jsonl"; write_q(q1, qs)
        A1 = tmp / "a1.jsonl"
        st = {}

        def o1():
            code, out, _ = run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", A1)
            e = [] if code == 0 else [f"answer exit {code}: {out[:120]}"]
            e += own_check(c1, qs, A1)
            code, rep = evaluate(a.tool, c1, q1, A1)
            if code != 0 or (rep or {}).get("status") != "pass":
                e.append(f"evaluate on correct answers should pass with exit 0, got {code} / {(rep or {}).get('status')}")
            n_un = sum(1 for q in qs if not q["expect"]["answerable"])
            if (rep or {}).get("counts", {}).get("correct_abstain") != n_un:
                e.append("correct_abstain count wrong")
            st["n_un"] = n_un
            return e
        check("o1", "clean control: baseline answers are exact quotes, abstains on traps, evaluator passes them", o1)

        def o2():
            # tampered answers built from the oracle's own truth, one known defect per question
            meta = {"kind": "meta", "schema": "solaris.grounded-answers/1", "producer": {"kind": "external_model", "name": "oracle-tamper", "executed_here": False}}
            recs, want = [], {}
            kinds = ["ok", "fabricated_quote", "altered_number", "uncited", "missed", "wrong_source", "bad_offsets", "paraphrase_ok", "relocatable"]
            ans = [q for q in qs if q["expect"]["answerable"]]
            others = sorted(w.docs)
            for i, q in enumerate(ans):
                k = kinds[i % len(kinds)]
                span, v = w.span(q["_doc"], q["_ai"])
                r = {"id": q["id"], "abstain": False, "answer": span["quote"], "citations": [dict(span)]}
                if k == "ok":
                    want[q["id"]] = "correct_supported"
                elif k == "fabricated_quote":
                    r["citations"][0]["quote"] = span["quote"].replace("has a", "is listed with a")
                    want[q["id"]] = "invalid_citation"
                elif k == "altered_number":
                    r["answer"] = span["quote"].replace(f" {v} ", f" {v}7 ")
                    want[q["id"]] = "unsupported_claim"
                elif k == "uncited":
                    r["citations"] = []
                    want[q["id"]] = "uncited"
                elif k == "missed":
                    r = {"id": q["id"], "abstain": True, "answer": "", "citations": []}
                    want[q["id"]] = "missed_answer"
                elif k == "wrong_source":
                    od = next(d for d in others if d != q["_doc"] and w.docs[d]["rows"])
                    s2, _ = w.span(od, w.docs[od]["rows"][0][0])
                    r = {"id": q["id"], "abstain": False, "answer": s2["quote"], "citations": [s2]}
                    want[q["id"]] = "wrong_source"
                elif k == "bad_offsets":
                    r["citations"][0]["start"] += 1
                    r["citations"][0]["end"] += 1
                    want[q["id"]] = "correct_supported"   # quote still unique in the doc: relocated, still valid
                elif k == "paraphrase_ok":
                    a_, u = ATTRS[q["_ai"]]
                    r["answer"] = f"{w.docs[q['_doc']]['name']} {a_}: {v} {u}."
                    want[q["id"]] = "correct_supported"
                else:
                    r["citations"][0]["start"], r["citations"][0]["end"] = 0, 5
                    want[q["id"]] = "correct_supported"
                recs.append(r)
            for j, q in enumerate([q for q in qs if not q["expect"]["answerable"]]):
                if j % 2 == 0:
                    recs.append({"id": q["id"], "abstain": False, "answer": f"It is 42 {ATTRS[q['_ai']][1]}.", "citations": []})
                    want[q["id"]] = "answered_unanswerable"
                else:
                    recs.append({"id": q["id"], "abstain": True, "answer": "", "citations": []})
                    want[q["id"]] = "correct_abstain"
            tp = tmp / "tampered.jsonl"
            tp.write_text("".join(json.dumps(x) + "\n" for x in [meta] + recs))
            code, rep = evaluate(a.tool, c1, q1, tp)
            got = verdicts(rep)
            bad = [f"{k}: want {v}, got {got.get(k)}" for k, v in sorted(want.items()) if got.get(k) != v]
            e = bad[:5]
            if code != 1:
                e.append(f"evaluate with defects should exit 1, got {code}")
            if "not executed" not in str(((rep or {}).get("provenance") or {}).get("evidence", "")):
                e.append("imported answers must be labelled as not executed by the evaluator")
            return e
        check("o2", "grader names every injected defect exactly (fabricated quote, altered number, uncited, missed, wrong source, hallucinated answer)", o2)

        def o3():
            e = []
            for s in (a.seed + 11, a.seed + 12):
                w2 = World(s, 60); c = w2.write(tmp / f"u{s}"); qq = w2.questions(120, s + 1)
                qp = tmp / f"u{s}.jsonl"; write_q(qp, qq); ap_ = tmp / f"ua{s}.jsonl"
                run(a.tool, "answer", "--corpus", c, "--questions", qp, "--out", ap_)
                e += [f"seed {s}: {x}" for x in own_check(c, qq, ap_)]
                code, rep = evaluate(a.tool, c, qp, ap_)
                if code != 0:
                    e.append(f"seed {s}: evaluate exit {code}")
            return e
        check("o3", "unseen seeds: answers exact and evaluator agrees", o3)

        def o4():
            v2 = World(a.seed, a.docs)          # same world, then edits
            rnd = random.Random(a.seed + 5)
            fns = sorted(v2.docs)
            changed, deleted, moved = set(), set(), set()
            for fn in rnd.sample(fns, len(fns) // 5):
                row = rnd.choice(v2.docs[fn]["rows"])
                row[1] = str(int(float(row[1])) + 1000)
                changed.add((fn, row[0]))
            for fn in rnd.sample([f for f in fns if not any(f == c[0] for c in changed)], len(fns) // 10):
                deleted.add(fn)
            for fn in rnd.sample([f for f in fns if f not in deleted], len(fns) // 4):
                v2.docs[fn]["preamble"] = ["Specifications revised in October 2026."]
                moved.add(fn)
            for fn in deleted:
                del v2.docs[fn]
            c2 = v2.write(tmp / "v2")
            q2 = []
            for q in qs:
                q = json.loads(json.dumps(q))
                if q["_doc"] in deleted and q["expect"]["answerable"]:
                    q["expect"] = {"answerable": False}
                elif q["expect"]["answerable"]:
                    _, v = v2.span(q["_doc"], q["_ai"])
                    q["expect"]["facts"] = [f"{v} {ATTRS[q['_ai']][1]}"]
                q2.append(q)
            qp2 = tmp / "q2.jsonl"; write_q(qp2, q2)
            want = {}
            for q, qn in zip(qs, q2):
                if not q["expect"]["answerable"]:
                    want[q["id"]] = "correct_abstain"
                elif q["_doc"] in deleted:
                    want[q["id"]] = "answered_unanswerable"
                elif (q["_doc"], q["_ai"]) in changed:
                    want[q["id"]] = "stale_citation"
                else:
                    want[q["id"]] = "correct_supported"
            code, rep = evaluate(a.tool, c2, qp2, A1)
            got = verdicts(rep)
            e = [f"{k}: want {v}, got {got.get(k)}" for k, v in sorted(want.items()) if got.get(k) != v][:5]
            if not any(r.get("citations") and r["citations"][0].get("status") == "relocated" for r in (rep or {}).get("results", [])):
                e.append("no relocated citation reported although lines moved")
            A2 = tmp / "a2.jsonl"
            run(a.tool, "answer", "--corpus", c2, "--questions", qp2, "--out", A2)
            e += [f"re-answer on v2: {x}" for x in own_check(c2, q2, A2)][:3]
            code, rep = evaluate(a.tool, c2, qp2, A2)
            if code != 0:
                e.append(f"re-answered v2 should pass, exit {code}")
            info["source_change"] = {"changed_facts": len(changed), "deleted_docs": len(deleted), "moved_docs": len(moved)}
            return e
        check("o4", "source change: stale citations named exactly, moved lines relocated, deleted docs make answers unsupported, re-answer passes", o4)

        def o5():
            ans = [q["id"] for q in qs]
            fp = tmp / "fault.json"
            fp.write_text(json.dumps({"retrieve": {ans[7]: 1, ans[150]: 2}}))
            J, O = tmp / "j.jsonl", tmp / "o5.jsonl"
            e = []
            code, out, _ = run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", O, "--journal", J, "--fault-plan", fp)
            if code != 3 or O.exists():
                e.append(f"first run with a failing tool step should exit 3 and write no answers, got {code}, exists {O.exists()}")
            code, out, _ = run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", O, "--journal", J, "--fault-plan", fp, "--resume")
            if code != 3:
                e.append(f"second failure of the same step should exit 3 again, got {code}")
            code, out, _ = run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", O, "--journal", J, "--fault-plan", fp, "--resume")
            if code != 0 or not O.exists() or O.read_bytes() != A1.read_bytes():
                e.append("after resuming, answers must be byte-identical to an unbroken run")
            dones = [l for l in J.read_text().splitlines() if '"kind": "done"' in l]
            if len(dones) != len(qs):
                e.append(f"journal has {len(dones)} done entries for {len(qs)} questions (duplicates or gaps)")
            return e
        check("o5", "recoverable tool failure: exit 3 with journal, resume completes byte-identical, no duplicate steps", o5)

        def o6():
            e = []
            fp = tmp / "fault1.json"; fp.write_text(json.dumps({"retrieve": {qs[3]["id"]: 1}}))
            J, O = tmp / "j6.jsonl", tmp / "o6.jsonl"
            run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", O, "--journal", J, "--fault-plan", fp)
            good = J.read_bytes()
            lines = good.split(b"\n")
            J.write_bytes(b"\n".join(lines[:3] + [b"{not json"] + lines[3:]))
            code, _, _ = run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", O, "--journal", J, "--resume")
            if code != 2 or O.exists():
                e.append(f"corrupted journal must be refused (exit 2, nothing written), got {code}")
            J.write_bytes(good)
            other = World(a.seed + 99, 20).write(tmp / "other")
            code, _, _ = run(a.tool, "answer", "--corpus", other, "--questions", q1, "--out", O, "--journal", J, "--resume")
            if code != 2:
                e.append(f"resume against a different snapshot must be refused, got {code}")
            J.write_bytes(good + b'{"kind": "done", "id": "q0')   # torn tail from a crash
            code, _, _ = run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", O, "--journal", J, "--resume", "--fault-plan", fp)
            if code != 0 or O.read_bytes() != A1.read_bytes():
                e.append(f"torn last journal line should be dropped and the run completed identically, got {code}")
            return e
        check("o6", "unsafe resume refused (corrupted journal, changed snapshot); torn tail recovered", o6)

        def o7():
            e = []
            _, rep = evaluate(a.tool, c1, q1, A1)
            prov = (rep or {}).get("provenance") or {}
            if "deterministic" not in str(prov.get("evidence", "")) or prov.get("baseline_reproduced") is not True:
                e.append("baseline answers must be labelled deterministic fixture behaviour, reproduced by a re-run")
            if "no model" not in str(prov.get("evaluator", "")):
                e.append("evaluator must state that no model or judge ran")
            meta, recs = read_answers(A1)
            un = tmp / "unlabelled.jsonl"
            un.write_text("".join(json.dumps(r) + "\n" for r in recs.values()))
            _, rep = evaluate(a.tool, c1, q1, un)
            if "unlabelled" not in str(((rep or {}).get("provenance") or {}).get("evidence", "")):
                e.append("an answers file without producer must be reported as unlabelled")
            # forged: keeps the baseline producer label but one answer was edited by hand
            fg = tmp / "forged-baseline.jsonl"
            first = sorted(recs)[0]
            forged = dict(recs[first]); forged["answer"] = (forged.get("answer") or "") + " Verified by staff."
            fg.write_text("".join(json.dumps(r) + "\n" for r in [meta] + [forged if k == first else recs[k] for k in sorted(recs)]))
            _, rep = evaluate(a.tool, c1, q1, fg)
            prov = (rep or {}).get("provenance") or {}
            if prov.get("baseline_reproduced") is not False or "unverified" not in str(prov.get("evidence", "")):
                e.append("a file that claims the baseline label but does not match a re-run must be reported unverified")
            return e
        check("o7", "provenance: deterministic baseline vs imported vs unlabelled answers are distinguished", o7)

        def o8():
            e = []
            O = tmp / "o8.jsonl"
            run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", O)
            if O.read_bytes() != A1.read_bytes():
                e.append("rerun is not byte-identical")
            sq = list(qs); random.Random(3).shuffle(sq)
            qs8 = tmp / "q8.jsonl"; write_q(qs8, sq)
            O2 = tmp / "o8b.jsonl"
            run(a.tool, "answer", "--corpus", c1, "--questions", qs8, "--out", O2)
            _, r1 = read_answers(A1); _, r2 = read_answers(O2)
            if len(r1) != len(qs) or sum(1 for r in r1.values() if r.get("abstain") is False) == 0:
                e.append("no real answers to compare (an empty file is trivially deterministic)")
            if r1 != r2:
                e.append("question order changes answers")
            _, rep1 = evaluate(a.tool, c1, q1, A1); _, rep2 = evaluate(a.tool, c1, qs8, O2)
            if verdicts(rep1) != verdicts(rep2):
                e.append("question order changes verdicts")
            return e
        check("o8", "deterministic and order-invariant", o8)

        def o9():
            e = []
            bad = tmp / "dupq.jsonl"
            bad.write_text(q1.read_text() + q1.read_text().splitlines()[0] + "\n")
            O = tmp / "o9.jsonl"
            code, _, _ = run(a.tool, "answer", "--corpus", c1, "--questions", bad, "--out", O)
            if code != 2 or O.exists():
                e.append(f"duplicate question ids should exit 2 with nothing written, got {code}")
            ln = tmp / "linked"; shutil.copytree(c1, ln)
            f0 = sorted(ln.iterdir())[0]; f0.unlink(); os.symlink(c1 / f0.name, f0)
            code, _, _ = run(a.tool, "answer", "--corpus", ln, "--questions", q1, "--out", O)
            if code != 2:
                e.append(f"symlinked source document should exit 2, got {code}")
            before = q1.read_bytes()
            code, _, _ = run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", q1)
            if code != 2 or q1.read_bytes() != before:
                e.append("--out onto the question file must be refused and leave it intact")
            return e
        check("o9", "invalid input refused with nothing written; inputs never overwritten", o9)

        def o10():
            big = World(a.seed + 31, a.scale_docs); cb = big.write(tmp / "big")
            qb = big.questions(a.scale_docs, a.seed + 32); qp = tmp / "qb.jsonl"; write_q(qp, qb)
            O1, O4 = tmp / "b1.jsonl", tmp / "b4.jsonl"
            code, _, s1 = run(a.tool, "answer", "--corpus", cb, "--questions", qp, "--out", O1)
            code4, _, s4 = run(a.tool, "answer", "--corpus", cb, "--questions", qp, "--out", O4, "--workers", "4")
            e = own_check(cb, qb, O1)[:4]
            if not O4.exists() or O1.read_bytes() != O4.read_bytes():
                e.append("1 worker and 4 workers differ")
            t0 = time.monotonic(); code, rep = evaluate(a.tool, cb, qp, O1); se = time.monotonic() - t0
            if code != 0:
                e.append(f"evaluate at scale exit {code}")
            if max(s1, s4, se) > a.scale_seconds:
                e.append(f"too slow: {max(s1, s4, se):.1f}s")
            info["scale"] = {"documents": len(big.docs), "questions": len(qb), "answer_s_1_worker": round(s1, 2),
                             "answer_s_4_workers": round(s4, 2), "evaluate_s": round(se, 2)}
            return e
        check("o10", "scale: thousands of documents and questions, 1 vs 4 workers byte-identical, within budget", o10)

        def o11():
            outs = [tmp / f"p{i}.jsonl" for i in range(4)]
            with cf.ThreadPoolExecutor(4) as ex:
                list(ex.map(lambda o: run(a.tool, "answer", "--corpus", c1, "--questions", q1, "--out", o), outs))
            reps = [tmp / f"r{i}.json" for i in range(4)]
            with cf.ThreadPoolExecutor(4) as ex:
                list(ex.map(lambda r: run(a.tool, "evaluate", "--corpus", c1, "--questions", q1, "--answers", A1, "--json", "--out", r), reps))
            e = []
            if len({o.read_bytes() for o in outs if o.exists()}) != 1 or not all(o.exists() for o in outs):
                e.append("parallel answer runs disagree or one is missing")
            if len({r.read_bytes() for r in reps if r.exists()}) != 1 or not all(r.exists() for r in reps):
                e.append("parallel evaluate runs disagree or one is missing")
            if outs[0].exists() and len(read_answers(outs[0])[1]) != len(qs):
                e.append("parallel answer output does not cover every question")
            if reps[0].exists() and len(json.loads(reps[0].read_text()).get("results", [])) != len(qs):
                e.append("parallel evaluate report does not cover every question")
            if list(tmp.glob(".*.tmp")):
                e.append("temporary files left behind")
            return e
        check("o11", "concurrency: parallel answer and evaluate runs agree byte for byte, no temp files left", o11)

    passed = sum(r["pass"] for r in results)
    summary = {"tool": a.tool, "seed": a.seed, "passed": passed, "total": len(results), "checks": results, "info": info}
    if a.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        for r in results:
            print(f"{'PASS' if r['pass'] else 'FAIL'} {r['id']} {r['title']}")
            for x in r["errors"]:
                print(f"     - {x}")
        for k, v in info.items():
            print(f"{k}: {v}")
        print(f"{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
