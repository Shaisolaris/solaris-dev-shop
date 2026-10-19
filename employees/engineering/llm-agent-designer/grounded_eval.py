#!/usr/bin/env python3
"""Offline grounded-answer evals over a supplied source snapshot (Solaris llm-agent-designer).

Two commands, Python 3.9+ standard library only, no network, no model:

  answer    deterministic extractive BASELINE: BM25 over source sentences; answers only when one
            sentence covers the question's key terms, otherwise abstains. Every answer is a quote
            with exact code-point offsets. It is fixture behaviour, not model intelligence.
            Each retrieval step is journaled; a failed tool step stops the run (exit 3) and
            `--resume` continues from the journal and gives the same bytes as an unbroken run.
  evaluate  grade ANY answers file (this baseline or an imported model/host output) against the
            snapshot and a question set: every citation must quote the snapshot exactly, every
            number in an answer must appear in its cited quotes, expected facts must be present,
            and unanswerable questions must be abstained on. Source changes are named.

Usage:
  grounded_eval.py answer   --corpus DIR --questions Q.jsonl --out A.jsonl [--journal J] [--resume]
                            [--workers N] [--fault-plan F.json] [--min-coverage 0.75]
  grounded_eval.py evaluate --corpus DIR --questions Q.jsonl --answers A.jsonl [--json] [--out R.json]
Exit codes: 0 all pass / run complete; 1 evaluated with failures; 2 invalid input (nothing written);
            3 tool step failed, journal kept, rerun with --resume.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import json
import math
import os
import re
import secrets
import stat
import sys
import unicodedata
try:
    import fcntl
except ImportError:  # pragma: no cover - not POSIX
    fcntl = None
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

TOOL_VERSION = "1.0.0"
ANSWERS_SCHEMA = "solaris.grounded-answers/1"
REPORT_SCHEMA = "solaris.grounded-eval-report/1"
JOURNAL_SCHEMA = "solaris.grounded-journal/2"
MAX_DOC_BYTES = 2 * 1024 * 1024
MAX_DOCS = 20000
MAX_QUESTIONS = 50000
DOC_SUFFIXES = (".md", ".txt")
STOP = set("""a an and are as at be been by can could do does did for from has have how i if in into is it its
of on or our than that the their them then there these this those to was were what when where which who whom
whose why will with would you your about after any all also may must should shall not no yes per each
many much long often""".split())
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
TOK_RE = re.compile(r"[a-z0-9]+(?:[.,'][a-z0-9]+)*")
END_RE = re.compile(r"[.!?]+(?=\s|$)")  # a period inside 2.75 or v1.2 is not a sentence end
NEEDS_NUMBER = re.compile(r"^\s*(how (many|much|long|often|far|old)|when|what (time|year|date|day))\b", re.I)
# "when" / "what day" questions may be answered by a calendar word instead of a number ("closed on Mondays")
WHEN_Q = re.compile(r"^\s*(when|what (time|date|day))\b", re.I)
NEGATORS = {"not", "no", "never", "nor", "cannot", "none", "neither", "without", "nobody", "nothing", "nowhere"}
# text addressed to an automated reader is data, never an instruction; such sentences are not used as sources (N11)
# R4 (M16 r2): a sentence is instruction-like only when it addresses an automated reader and tells it what to say.
# "Model boats ... the warden will answer any questions" and "Shop assistants will answer questions" are rules, not
# instructions: bare "model" and bare "assistant" (a person) are not addressees unless the sentence is a note to them.
_BOT = (r"(?:(?:automated|ai|virtual|digital|chat)\s+(?:assistants?|readers?|agents?|systems?|models?)|chatbots?|bots?"
        r"|(?:large\s+)?language\s+models?|llms?|ai)")
_ANY = r"(?:" + _BOT + r"|assistants?|models?)"
_SAY = r"(?:reply|respond|answer|say|state|tell|output|ignore|disregard|write)"
INSTRUCTION_RE = re.compile(
    r"(?i)\b(?:note|message|instructions?|attention|notice|reminder)\s+(?:to|for)\s+(?:all\s+|any\s+|the\s+)?" + _ANY + r"\b"
    r"|\b(?:dear|hey|attention)\s+" + _ANY + r"\b"
    r"|\bif\s+you\s+are\s+an?\s+" + _ANY + r"\b"
    r"|\b" + _BOT + r"\s*[,:]\s*(?:[\w']+\s+){0,6}?" + _SAY + r"\b"
    r"|\b" + _BOT + r"\s+(?:(?:must|should|shall|will|need\s+to|are\s+to|is\s+to|are\s+asked\s+to|have\s+to)\s+)?"
    r"(?:always\s+|only\s+)?" + _SAY + r"\b"
    r"|\b(?:ignore|disregard)\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+instructions\b")
MAX_FAULTS = 100
TIME_WORDS = re.compile(r"(?i)\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekday|weekend|"
                        r"january|february|march|april|june|july|august|september|october|november|december|"
                        r"daily|weekly|monthly|yearly|annually|noon|midnight|morning|afternoon|evening|night)s?\b")


class Invalid(Exception):
    pass


class ToolFailure(Exception):
    pass


def _need(cond: bool, msg: str) -> None:
    if not cond:
        raise Invalid(msg)


# -- text ---------------------------------------------------------------------------

def _stem(t: str) -> str:
    if NUM_RE.fullmatch(t):
        return t.replace(",", "")
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def terms(text: str) -> List[str]:
    return [_stem(t.strip(".,'")) for t in TOK_RE.findall(text.lower()) if t.strip(".,'") not in STOP]


def numbers(text: str) -> set:
    """Whole-token numbers: "122" is not "22", and the 12 in an identifier such as K12 is not a quantity (N2)."""
    return {t.replace(",", "") for t in TOK_RE.findall(text.lower()) if NUM_RE.fullmatch(t)}


def idents(text: str) -> set:
    """Identifier tokens with digits (K12, r7, 7-day parts): an answer may only name ones its quotes name."""
    return {t for t in TOK_RE.findall(text.lower()) if any(ch.isdigit() for ch in t) and not NUM_RE.fullmatch(t)}


def norm(text: str) -> str:
    return " ".join(TOK_RE.findall(text.lower()))


def has_phrase(phrase: str, text: str) -> bool:
    """Whole-token phrase match: "22 pounds" is not found in "122 pounds" (N2)."""
    return f" {norm(phrase)} " in f" {norm(text)} "


def seq(text: str) -> List[str]:
    """Every token, stemmed, stopwords kept (for neighbours and number context)."""
    return [_stem(t.strip(".,'")) for t in TOK_RE.findall(text.lower())]


def negated(text: str) -> bool:
    return any(t in NEGATORS or t.endswith("n't") for t in TOK_RE.findall(text.lower().replace("\u2019", "'")))


def _neg_bindings(text: str) -> List[Optional[str]]:
    """Each negator with the next content word it governs ("must not light" -> light) (M16 r2 R1). A leading
    "No," that answers the question is not a negator; "No dogs are allowed" keeps its "no"."""
    low = text.lower().replace("\u2019", "'")
    toks = [t.strip(".,'") for t in TOK_RE.findall(low)]
    answer_no = re.match(r"\s*no\s*[,;:.!]", low) is not None

    def isneg(t: str) -> bool:
        return t in NEGATORS or t.endswith("n't")
    return [next((_stem(x) for x in toks[i + 1:] if x not in STOP and not isneg(x)), None)
            for i, t in enumerate(toks) if isneg(t) and not (i == 0 and t == "no" and answer_no)]


def number_context(text: str) -> List[Tuple[str, set, Optional[str]]]:
    """For each number: (number, content terms since the previous number (at most 6), next token)."""
    toks = seq(text)
    out = []
    since: List[str] = []
    for i, t in enumerate(toks):
        if NUM_RE.fullmatch(t):
            nxt = toks[i + 1] if i + 1 < len(toks) and not NUM_RE.fullmatch(toks[i + 1]) else None
            out.append((t.replace(",", ""), set(since[-6:]), nxt))
            since = []
        elif t not in STOP:
            since.append(t)
    return out


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# -- inputs -------------------------------------------------------------------------

def _regular(p: Path, what: str, limit: int) -> bytes:
    try:
        st = os.lstat(p)
    except FileNotFoundError:
        raise Invalid(f"{what}: {p.name} does not exist") from None
    _need(not stat.S_ISLNK(st.st_mode), f"{what}: {p.name} is a symlink; pass the real file")
    _need(stat.S_ISREG(st.st_mode), f"{what}: {p.name} is not a regular file")
    _need(st.st_size <= limit, f"{what}: {p.name} is larger than {limit} bytes")
    fd = os.open(p, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as fh:
        return fh.read(limit + 1)


def load_corpus(d: str) -> Dict[str, Any]:
    base = Path(d)
    _need(base.is_dir() and not base.is_symlink(), f"corpus: {base.name} is not a folder")
    docs = {}
    for p in sorted(base.iterdir()):
        if p.name.startswith(".") or p.suffix not in DOC_SUFFIXES:
            continue
        raw = _regular(p, "corpus", MAX_DOC_BYTES)
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise Invalid(f"corpus: {p.name} is not UTF-8 (byte {exc.start})") from None
        docs[p.name] = {"text": text, "sha256": sha(raw)}
        _need(len(docs) <= MAX_DOCS, f"corpus: more than {MAX_DOCS} documents")
    _need(docs, "corpus: no .md or .txt documents")
    listing = "".join(f"{n}\0{v['sha256']}\n" for n, v in sorted(docs.items()))
    return {"docs": docs, "sha256": sha(listing.encode())}


def _jsonl(raw: bytes, what: str) -> List[Dict[str, Any]]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Invalid(f"{what}: not UTF-8") from None
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line, object_pairs_hook=_no_dupes, parse_constant=_no_const)
        except json.JSONDecodeError:
            raise Invalid(f"{what}: line {i} is not JSON") from None
        _need(isinstance(rec, dict), f"{what}: line {i} is not an object")
        out.append(rec)
    return out


def _no_dupes(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise Invalid(f"duplicate key {k!r}")
        d[k] = v
    return d


def _no_const(name):
    raise Invalid(f"non-finite number {name}")


def load_questions(path: str) -> Tuple[List[Dict[str, Any]], str]:
    raw = _regular(Path(path), "questions", 64 * 1024 * 1024)
    qs = _jsonl(raw, "questions")
    _need(0 < len(qs) <= MAX_QUESTIONS, f"questions: need 1..{MAX_QUESTIONS} questions")
    seen = set()
    for q in qs:
        qid = q.get("id")
        _need(isinstance(qid, str) and qid and qid not in seen, f"questions: id {qid!r} missing or repeated")
        seen.add(qid)
        _need(isinstance(q.get("question"), str) and q["question"].strip(), f"questions: {qid} has no question text")
        exp = q.get("expect")
        _need(isinstance(exp, dict) and isinstance(exp.get("answerable"), bool), f"questions: {qid} needs expect.answerable true/false")
        if exp["answerable"]:
            facts = exp.get("facts")
            _need(isinstance(facts, list) and facts and all(isinstance(f, str) and norm(f) for f in facts),
                  f"questions: {qid} answerable needs expect.facts (non-empty strings)")
            sd = exp.get("support_docs", [])
            _need(isinstance(sd, list) and all(isinstance(x, str) for x in sd), f"questions: {qid} support_docs must be a list of file names")
    return qs, sha(raw)


# -- index + baseline answerer --------------------------------------------------------

def sentence_spans(text: str) -> List[Tuple[int, int]]:
    spans = []
    pos = 0
    for line in text.split("\n"):
        start = pos
        for m in END_RE.finditer(line):
            spans.append((start, pos + m.end()))
            start = pos + m.end()
        if line[start - pos:].strip():
            spans.append((start, pos + len(line)))
        pos += len(line) + 1
    return spans


class Index:
    """BM25 over sentences. Sentence offsets are code-point offsets into the decoded document."""

    def __init__(self, corpus: Dict[str, Any]):
        self.sents: List[Tuple[str, int, int, str]] = []
        self.toks: List[set] = []
        self.seqs: List[List[str]] = []
        self.skipped: List[Tuple[str, int, int]] = []
        post: Dict[str, List[Tuple[int, int]]] = {}
        lengths = []
        for name, doc in sorted(corpus["docs"].items()):
            text = doc["text"]
            for s, e in sentence_spans(text):
                while s < e and text[s].isspace():
                    s += 1
                while e > s and text[e - 1].isspace():
                    e -= 1
                frag = text[s:e]
                if frag.lstrip().startswith("#"):
                    continue  # headings are context, not statements
                ts = terms(frag)
                if not ts:
                    continue
                if INSTRUCTION_RE.search(frag):
                    self.skipped.append((name, s, e))
                    continue
                sid = len(self.sents)
                self.sents.append((name, s, e, frag))
                self.toks.append(set(ts))
                self.seqs.append(seq(frag))
                lengths.append(len(ts))
                tf: Dict[str, int] = {}
                for t in ts:
                    tf[t] = tf.get(t, 0) + 1
                for t, c in tf.items():
                    post.setdefault(t, []).append((sid, c))
        self.post = post
        self.len = lengths
        self.avg = (sum(lengths) / len(lengths)) if lengths else 1.0
        self.n = len(lengths)

    def search(self, q_terms: List[str], k: int = 5) -> List[Tuple[float, int]]:
        scores: Dict[int, float] = {}
        for t in set(q_terms):
            pl = self.post.get(t)
            if not pl:
                continue
            idf = math.log(1 + (self.n - len(pl) + 0.5) / (len(pl) + 0.5))
            for sid, c in pl:
                denom = c + 1.2 * (1 - 0.75 + 0.75 * self.len[sid] / self.avg)
                scores[sid] = scores.get(sid, 0.0) + idf * c * 2.2 / denom
        ranked = sorted(scores.items(), key=lambda x: (-round(x[1], 9), self.sents[x[0]][0], self.sents[x[0]][1]))
        return [(round(s, 6), sid) for sid, s in ranked[:k]]


def baseline_answer(idx: Index, corpus: Dict[str, Any], q: Dict[str, Any], min_cov: float) -> Dict[str, Any]:
    key = sorted(set(terms(q["question"])))
    rec: Dict[str, Any] = {"id": q["id"]}
    if not key:
        rec.update(abstain=True, reason="no_key_terms", answer="", citations=[])
        return rec
    hits = idx.search(key, k=10)
    need_num = bool(NEEDS_NUMBER.search(q["question"]))
    when_q = bool(WHEN_Q.search(q["question"]))

    def quantities(text: str) -> set:
        found = set(numbers(text))
        if when_q:
            found |= {m.group(1).lower() for m in TIME_WORDS.finditer(text)}
            found |= {"may"} if re.search(r"\bMay\b(?=\s+\d|\s*$|[.,;])", text) else set()  # the month, not the verb
        return found
    good = []
    # identifiers must match exactly, not just most key terms: tokens with digits (K241, 65, 7-day)
    # and capitalised names after the first word (Heron vs Godwit K241)
    ids = {t for t in key if any(ch.isdigit() for ch in t)}
    ids |= {_stem(w.lower()) for w in re.findall(r"(?<!^)(?<![.?!]\s)\b[A-Z][a-zA-Z]+", q["question"].strip())} & set(key)
    qseq = seq(q["question"])

    def near_miss(sid: int) -> bool:
        """An uncovered question term next to a covered one while the sentence has a different word in that
        place is a sibling, not a match (N4): a modifier before it ("quarter plot" vs "full plot"), or a word
        after it that the snapshot uses elsewhere ("Westfield shop" vs "Westfield site")."""
        st, ss = idx.toks[sid], idx.seqs[sid]
        for i, w in enumerate(qseq):
            if w in STOP or w in st or NUM_RE.fullmatch(w):
                continue
            for j, side in ((i + 1, -1), (i - 1, 1)):
                if side == 1 and w not in idx.post:
                    continue
                if 0 <= j < len(qseq) and qseq[j] in st and qseq[j] not in STOP:
                    t = qseq[j]
                    nb = [ss[k + side] for k in range(len(ss)) if ss[k] == t and 0 <= k + side < len(ss)]
                    if nb and w not in nb and any(x not in STOP for x in nb):
                        return True
        return False

    for score, sid in hits:
        cov = len(set(key) & idx.toks[sid]) / len(key)
        if cov + 1e-9 < min_cov or not ids <= idx.toks[sid]:
            continue
        if near_miss(sid):
            continue
        if need_num and not quantities(idx.sents[sid][3]):
            continue
        good.append((cov, score, sid))
    if not good:
        best = hits[0] if hits else None
        rec.update(abstain=True, reason="no_sentence_covers_the_question", answer="", citations=[],
                   best_coverage=round(len(set(key) & idx.toks[best[1]]) / len(key), 3) if best else 0.0)
        return rec
    good.sort(key=lambda g: (-g[0], -g[1], idx.sents[g[2]][0], idx.sents[g[2]][1]))
    top = good[0]
    rivals = [g for g in good[1:] if g[0] == top[0] and idx.sents[g[2]][0] != idx.sents[top[2]][0]]
    top_q = quantities(idx.sents[top[2]][3])
    # sources that disagree on a number make the baseline abstain, however the question is phrased (N3)
    if any(quantities(idx.sents[g[2]][3]) != top_q and (need_num or (top_q and quantities(idx.sents[g[2]][3]))) for g in rivals):
        rec.update(abstain=True, reason="conflicting_sources", answer="",
                   citations=[_cite(idx, corpus, top[2])] + [_cite(idx, corpus, g[2]) for g in rivals[:2]])
        return rec
    rec.update(abstain=False, answer=idx.sents[top[2]][3], citations=[_cite(idx, corpus, top[2])],
               coverage=round(top[0], 3), score=top[1])
    return rec


def _cite(idx: Index, corpus: Dict[str, Any], sid: int) -> Dict[str, Any]:
    name, s, e, frag = idx.sents[sid]
    return {"doc": name, "start": s, "end": e, "quote": frag, "doc_sha256": corpus["docs"][name]["sha256"]}


# -- journal ---------------------------------------------------------------------------

def _chain(prev: str, obj: Dict[str, Any]) -> str:
    body = {k: v for k, v in obj.items() if k != "chain"}
    return sha((prev + "\n" + json.dumps(body, sort_keys=True)).encode("utf-8"))


class Journal:
    """Append-only, hash-chained journal: each entry carries sha256(previous chain + entry), so a torn,
    reordered or hand-edited entry is detected on resume. It detects corruption and edits, not a forger
    who recomputes the chain; evaluate still re-runs the baseline to verify a resumed answers file."""

    def __init__(self, fh, prev: str):
        self.fh, self.prev = fh, prev

    def append(self, obj: Dict[str, Any]) -> None:
        obj = dict(obj)
        obj["chain"] = self.prev = _chain(self.prev, obj)
        self.fh.write((json.dumps(obj, sort_keys=True) + "\n").encode("utf-8"))
        self.fh.flush()
        os.fsync(self.fh.fileno())


def read_journal(path: Path, header: Dict[str, Any], ids: Optional[set] = None,
                 raw: Optional[bytes] = None) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int], int, str]:
    if raw is None:
        raw = _regular(path, "journal", 256 * 1024 * 1024)
    lines = raw.split(b"\n")
    torn = 0
    if lines and lines[-1] != b"":
        torn = 1  # last write was interrupted mid-line: not trusted, step will be redone
    lines = [l for l in lines[:-1]] if lines else []
    _need(lines, "journal: empty; start without --resume")
    try:
        recs = [json.loads(l) for l in lines]
    except json.JSONDecodeError:
        raise Invalid("journal: a complete line is not JSON (corrupted); refusing to resume") from None
    _need(all(isinstance(r, dict) for r in recs), "journal: an entry is not an object")
    prev = ""
    for i, r in enumerate(recs, 1):
        _need(r.get("chain") == _chain(prev, r), f"journal: entry {i} fails its integrity check (edited, reordered or corrupted); "
              "refusing to resume; start a new journal")
        prev = r["chain"]
    h = recs[0]
    _need(h.get("schema") == JOURNAL_SCHEMA, "journal: not a grounded-eval journal")
    for k in ("corpus_sha256", "questions_sha256", "min_coverage", "tool_version"):
        _need(h.get(k) == header[k], f"journal: {k} differs from this run (source or settings changed); start a new journal")
    done: Dict[str, Dict[str, Any]] = {}
    fails: Dict[str, int] = {}
    for r in recs[1:]:
        if r.get("kind") == "done":
            _need(isinstance(r.get("record"), dict) and r.get("id") not in done, "journal: duplicate or malformed done entry")
            _need(r["record"].get("id") == r["id"] and (ids is None or r["id"] in ids), "journal: a done entry names an unknown question")
            done[r["id"]] = r["record"]
        elif r.get("kind") == "failed":
            fails[r["id"]] = fails.get(r["id"], 0) + 1
        else:
            raise Invalid("journal: unknown entry kind")
    return done, fails, torn, prev


# -- answer command ---------------------------------------------------------------------

def run_answer(a) -> int:
    corpus = load_corpus(a.corpus)
    qs, qsha = load_questions(a.questions)
    _need(0 < a.min_coverage <= 1, "--min-coverage must be in (0, 1]")
    _need(1 <= a.workers <= 32, "--workers must be 1..32")
    fault: Dict[str, int] = {}
    if a.fault_plan:
        fp = json.loads(_regular(Path(a.fault_plan), "fault plan", 1024 * 1024).decode("utf-8"), object_pairs_hook=_no_dupes)
        _need(isinstance(fp, dict) and isinstance(fp.get("retrieve", {}), dict), "fault plan: {\"retrieve\": {question_id: failures}}")
        for k, v in fp.get("retrieve", {}).items():
            _need(isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= MAX_FAULTS,
                  f"fault plan: failures for {k!r} must be a whole number 0..{MAX_FAULTS}")
            fault[k] = v
    inputs = [Path(a.questions)] + [Path(a.corpus) / n for n in corpus["docs"]] + ([Path(a.fault_plan)] if a.fault_plan else [])
    out = _check_target(Path(a.out), inputs, Path(a.corpus))
    header = {"schema": JOURNAL_SCHEMA, "corpus_sha256": corpus["sha256"], "questions_sha256": qsha,
              "min_coverage": a.min_coverage, "tool_version": TOOL_VERSION}
    jpath = Path(a.journal) if a.journal else None
    done: Dict[str, Dict[str, Any]] = {}
    fails: Dict[str, int] = {}
    torn = 0
    jfh = None
    jr: Optional[Journal] = None
    try:
        if jpath:
            jpath = _check_target(jpath, inputs + [out], Path(a.corpus))
            _need(jpath != out, "--journal and --out name the same file; give them different names")
        if a.resume:
            _need(jpath is not None and jpath.exists(), "--resume needs an existing --journal")
            _regular(jpath, "journal", 256 * 1024 * 1024)
            jfh = open(jpath, "r+b")
            _lock(jfh, jpath)
            raw = jfh.read()
            done, fails, torn, prev = read_journal(jpath, header, {q["id"] for q in qs}, raw)
            if torn:  # drop the torn tail so the journal stays line-valid
                jfh.truncate(raw.rfind(b"\n") + 1)
            jfh.seek(0, os.SEEK_END)
            jr = Journal(jfh, prev)
        elif jpath:
            _need(not jpath.exists(), f"journal: {jpath.name} exists; pass --resume or remove it")
            fd = os.open(jpath, os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
            jfh = os.fdopen(fd, "r+b")
            _lock(jfh, jpath)
            jr = Journal(jfh, "")
            jr.append(header)
    except BaseException:
        if jfh:
            jfh.close()
        raise
    idx = Index(corpus)
    todo = [q for q in qs if q["id"] not in done]

    def step(q):
        attempt = fails.get(q["id"], 0) + 1
        if fault.get(q["id"], 0) >= attempt:
            raise ToolFailure(f"retrieval tool failed for {q['id']} (attempt {attempt}, injected by fault plan)")
        return baseline_answer(idx, corpus, q, a.min_coverage)

    failed = None
    try:
        with cf.ThreadPoolExecutor(a.workers) as ex:
            futs = {ex.submit(step, q): q for q in todo}
            for fut in cf.as_completed(futs):  # journal order may vary; output order never does
                q = futs[fut]
                try:
                    rec = fut.result()
                except ToolFailure as exc:
                    failed = failed or str(exc)
                    if jr:
                        jr.append({"kind": "failed", "id": q["id"], "error": str(exc)})
                    continue
                done[q["id"]] = rec
                if jr:
                    jr.append({"kind": "done", "id": q["id"], "record": rec})
        if failed:
            sys.stdout.write(f"tool step failed: {failed}\n{len(done)}/{len(qs)} questions done; "
                             f"{'journal kept, rerun with --resume' if jpath else 'no journal: rerun from the start'}\n")
            return 3
        meta = {"kind": "meta", "schema": ANSWERS_SCHEMA, "corpus_sha256": corpus["sha256"], "questions_sha256": qsha,
                "documents": {n: d["sha256"] for n, d in sorted(corpus["docs"].items())},
                "producer": {"kind": "deterministic_baseline", "tool": "grounded_eval.py", "version": TOOL_VERSION,
                             "method": "BM25 sentence retrieval + key-term coverage; extractive, no model",
                             "min_coverage": a.min_coverage, "executed_here": True}}
        if idx.skipped:
            meta["skipped_instruction_like_sentences"] = [{"doc": n, "start": s, "end": e} for n, s, e in idx.skipped]
        body = json.dumps(meta, sort_keys=True) + "\n" + "".join(json.dumps(done[q["id"]], sort_keys=True) + "\n" for q in qs)
        _write_atomic(out, body.encode("utf-8"))  # written while the journal lock is held
    finally:
        if jfh:
            jfh.close()
    n_abs = sum(1 for q in qs if done[q["id"]]["abstain"])
    sys.stdout.write(f"answered {len(qs) - n_abs}, abstained {n_abs} of {len(qs)}"
                     f"{f'; resumed with {len(qs) - len(todo)} from the journal' if a.resume else ''}"
                     f"{f'; dropped {torn} torn journal line' if torn else ''}\n")
    return 0


# -- evaluate command ---------------------------------------------------------------------

VERDICTS = ("correct_supported", "correct_abstain", "missed_answer", "answered_unanswerable", "invalid_citation",
            "stale_citation", "uncited", "unsupported_claim", "wrong_source", "incorrect", "missing_record")
PASSING = ("correct_supported", "correct_abstain")


def check_citation(c: Any, corpus: Dict[str, Any], other_snapshot: Any = True) -> Tuple[str, str]:
    """Return (status, detail): valid | relocated | stale | invalid. A missing quote is called stale only
    when the answers file declares the snapshot it was made for and the citation's doc_sha256 is that
    snapshot's hash of the document; otherwise a mismatching doc_sha256 cannot show that the source
    changed, and the quote is invalid (N7, M16 r2 R3). other_snapshot is the declared {doc: sha256} map,
    or a bool for callers that have already decided."""
    if not isinstance(c, dict) or not isinstance(c.get("doc"), str) or not isinstance(c.get("quote"), str) or not c["quote"]:
        return "invalid", "malformed citation"
    doc = corpus["docs"].get(c["doc"])
    recorded = c.get("doc_sha256")
    if isinstance(other_snapshot, dict):  # the declared document must carry the hash the citation records
        other_snapshot = isinstance(recorded, str) and other_snapshot.get(c["doc"]) == recorded
    if doc is None:
        if recorded and other_snapshot:
            return "stale", f"{c['doc']} no longer in the snapshot"
        return "invalid", f"{c['doc']} not in the snapshot"
    s, e = c.get("start"), c.get("end")
    text = doc["text"]
    if isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(text) and text[s:e] == c["quote"]:
        return "valid", ""
    n = text.count(c["quote"])
    if n == 1:
        return "relocated", f"quote found at {text.index(c['quote'])} instead of {s}"
    if recorded and recorded != doc["sha256"] and other_snapshot:
        return "stale", f"{c['doc']} changed since the answer was made and the quote is gone"
    if recorded and recorded != doc["sha256"]:
        return "invalid", ("quote is not in the snapshot; its doc_sha256 differs, but the answers file does not say it was "
                           "made for another snapshot, so a source change cannot be shown")
    return "invalid", "quote is not in the snapshot" if n == 0 else "offsets do not match and quote is ambiguous"


def _locate(c: Dict[str, Any], st: str, text: str) -> int:
    return c["start"] if st == "valid" else text.index(c["quote"])


def _support(answer: str, ok: List[Dict[str, Any]], sts: List[str], corpus: Dict[str, Any]) -> Optional[str]:
    """Lexical checks that the answer says what its quotes say (N1, N2). Returns a problem or None."""
    sents = []
    for c, st in zip(ok, sts):
        text = corpus["docs"][c["doc"]]["text"]
        s0 = _locate(c, st, text)
        e0 = s0 + len(c["quote"])
        span = next(((s, e) for s, e in sentence_spans(text) if s <= s0 and e0 <= e), None)
        if span is None:
            return f"a quote from {c['doc']} spans more than one sentence; quote one sentence (or part of one) per citation"
        sents.append(text[span[0]:span[1]])
    if negated(answer) != any(negated(x) for x in sents):
        return ("the answer drops a negation that its cited sentence has" if not negated(answer)
                else "the answer adds a negation that its cited sentences do not have")
    # R1: same presence is not same meaning; a negator that moved, or a new one, must govern what the source negates
    a_neg, s_neg = _neg_bindings(answer), [b for x in sents for b in _neg_bindings(x)]
    if any(b not in s_neg for b in a_neg):
        return "the answer negates something its cited sentence does not negate (a negation was added or moved)"
    a_words = set(seq(answer))
    if any(b is not None and b in a_words and b not in a_neg for b in s_neg):
        return "the answer asserts a word that its cited sentence negates (a negation was dropped or moved)"
    ctxs = [(c["quote"], number_context(c["quote"]), set(terms(x))) for c, x in zip(ok, sents)]
    for n, actx, anext in number_context(answer):
        fits = False
        for quote, qctx, sterms in ctxs:
            for qn, qc, qnext in qctx:
                if qn != n:
                    continue
                if anext is not None and anext not in STOP and qnext is not None and _stem(anext) != _stem(qnext):
                    continue  # "12 months" is not "12 troughs"
                if (actx & sterms) - qc:
                    continue  # the number is attached to another subject in the quote ("half plot ... 64")
                fits = True
        if not fits:
            return f"the number {n} is not stated, with the same subject and unit, in one cited quote"
    return None


def grade(q: Dict[str, Any], r: Optional[Dict[str, Any]], corpus: Dict[str, Any], other_snapshot: Any = True) -> Dict[str, Any]:
    exp = q["expect"]
    out: Dict[str, Any] = {"id": q["id"], "answerable": exp["answerable"]}
    if r is None:
        out.update(verdict="missing_record")
        return out
    abstain = r.get("abstain") is True
    asserted = isinstance(r.get("answer"), str) and bool(r["answer"].strip())
    out["abstained"] = abstain
    if abstain and asserted:
        out["abstain_note"] = "abstain is true but an answer was asserted; graded as an answer (N6)"
        abstain = False
        out["abstained"] = False
    if not exp["answerable"]:
        out["verdict"] = "correct_abstain" if abstain else "answered_unanswerable"
        return out
    if abstain:
        out["verdict"] = "missed_answer"
        return out
    answer = r.get("answer") if isinstance(r.get("answer"), str) else ""
    cites = r.get("citations") if isinstance(r.get("citations"), list) else []
    checks = [check_citation(c, corpus, other_snapshot) for c in cites]
    out["citations"] = [{"doc": c.get("doc") if isinstance(c, dict) else None, "status": st, **({"detail": d} if d else {})}
                        for c, (st, d) in zip(cites, checks)]
    ok = [c for c, (st, _) in zip(cites, checks) if st in ("valid", "relocated")]
    if not cites:
        out["verdict"] = "uncited"
        return out
    if any(st == "stale" for st, _ in checks) and not ok:
        out["verdict"] = "stale_citation"
        return out
    if len(ok) != len(cites):
        out["verdict"] = "stale_citation" if any(st == "stale" for st, _ in checks) else "invalid_citation"
        return out
    quoted = " ".join(c["quote"] for c in ok)
    q_nums, a_nums = numbers(quoted), numbers(answer)
    a_terms = set(terms(answer))
    cov = (len(a_terms & set(terms(quoted))) / len(a_terms)) if a_terms else 0.0
    a_ids = idents(answer) - idents(quoted)
    out["support"] = {"numbers_not_in_quotes": sorted(a_nums - q_nums), "content_coverage": round(cov, 3)}
    if a_ids:
        out["support"]["identifiers_not_in_quotes"] = sorted(a_ids)
    if a_nums - q_nums or a_ids or cov < 0.6 or not a_terms:
        out["verdict"] = "unsupported_claim"
        return out
    problem = _support(answer, ok, [st for st, _ in checks if st in ("valid", "relocated")], corpus)
    if problem:
        out["support"]["problem"] = problem
        out["verdict"] = "unsupported_claim"
        return out
    sd = exp.get("support_docs") or []
    if sd and not any(c["doc"] in sd for c in ok):
        out["verdict"] = "wrong_source"
        return out
    missing = [f for f in exp["facts"] if not has_phrase(f, answer) or not any(has_phrase(f, c["quote"]) for c in ok)]
    if missing:
        out.update(verdict="incorrect", missing_facts=missing)
        return out
    out["verdict"] = "correct_supported"
    return out


def _corpus_hash(docs: Dict[str, str]) -> str:
    return sha("".join(f"{n}\0{h}\n" for n, h in sorted(docs.items())).encode())


def declared_snapshot(meta: Optional[Dict[str, Any]], corpus: Dict[str, Any]) -> Tuple[Optional[Dict[str, str]], Optional[str]]:
    """The {doc: sha256} snapshot an answers file says it was made for, when that differs from this one and is
    self-consistent: its document list must reproduce meta.corpus_sha256. A bare corpus_sha256 is one free field
    and is not enough to call a missing quote stale (M16 r2 R3). Returns (docs or None, note or None)."""
    if not meta or not isinstance(meta.get("corpus_sha256"), str) or meta["corpus_sha256"] == corpus["sha256"]:
        return None, None
    docs = meta.get("documents")
    hexok = lambda h: isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h) is not None
    if (isinstance(docs, dict) and docs and all(isinstance(n, str) and hexok(h) for n, h in docs.items())
            and _corpus_hash(docs) == meta["corpus_sha256"]):
        return dict(docs), None
    return None, ("the answers file names another snapshot, but its documents list does not reproduce that "
                  "corpus_sha256, so missing quotes are reported invalid, not stale")


def run_evaluate(a) -> Tuple[int, Dict[str, Any], str]:
    corpus = load_corpus(a.corpus)
    qs, qsha = load_questions(a.questions)
    araw = _regular(Path(a.answers), "answers", 256 * 1024 * 1024)
    recs = _jsonl(araw, "answers")
    _need(recs, "answers: empty file")
    meta = recs[0] if recs[0].get("kind") == "meta" else None
    body = recs[1:] if meta else recs
    by_id: Dict[str, Dict[str, Any]] = {}
    for r in body:
        _need(isinstance(r.get("id"), str), "answers: a record has no id")
        _need(r["id"] not in by_id, f"answers: id {r['id']} answered twice")
        by_id[r["id"]] = r
    known = {q["id"] for q in qs}
    extra = sorted(set(by_id) - known)
    declared, declared_note = declared_snapshot(meta, corpus)
    rows = [grade(q, by_id.get(q["id"]), corpus, declared if declared is not None else False) for q in qs]
    counts = {v: 0 for v in VERDICTS}
    for row in rows:
        counts[row["verdict"]] += 1
    n_ans = sum(1 for q in qs if q["expect"]["answerable"])
    n_un = len(qs) - n_ans
    abst = [row for row in rows if row.get("abstained")]
    cit = [c for row in rows for c in row.get("citations", [])]
    producer = (meta or {}).get("producer") if isinstance((meta or {}).get("producer"), dict) else None
    verified = None
    if producer and producer.get("kind") == "deterministic_baseline":
        # a file can claim anything; the baseline is deterministic, so re-run it here and compare
        mc = producer.get("min_coverage")
        same_inputs = meta.get("corpus_sha256") == corpus["sha256"] and meta.get("questions_sha256") == qsha
        if same_inputs and isinstance(mc, (int, float)) and not isinstance(mc, bool) and 0 < mc <= 1:
            idx = Index(corpus)
            verified = len(body) == len(qs) and all(
                json.dumps(by_id.get(q["id"]), sort_keys=True) == json.dumps(baseline_answer(idx, corpus, q, float(mc)), sort_keys=True)
                for q in qs)
        else:
            verified = False
        if verified:
            evidence = "deterministic fixture behaviour (extractive baseline, no model; re-run here and matched)"
        elif same_inputs:
            evidence = "claims to be the deterministic baseline but does not match a re-run here; unverified, treat as imported"
        else:
            evidence = ("deterministic baseline output made for a different snapshot or question file; "
                        "unverified here (re-run the baseline to compare)")
    elif producer:
        evidence = "imported output (producer as named by the file; not executed or verified by this evaluator)"
    else:
        evidence = "unlabelled answers file (producer unknown)"
    notes = []
    if meta and meta.get("corpus_sha256") != corpus["sha256"]:
        notes.append("answers were produced against a different snapshot; changed sources are reported per citation")
    if declared_note:
        notes.append(declared_note)
    if meta and meta.get("questions_sha256") not in (None, qsha):
        notes.append("answers were produced for a different question file")
    if extra:
        notes.append(f"{len(extra)} answer records match no question and were ignored")
    rep = {
        "schema": REPORT_SCHEMA, "tool_version": TOOL_VERSION,
        "inputs": {"corpus_sha256": corpus["sha256"], "documents": len(corpus["docs"]), "questions_sha256": qsha,
                   "answers_sha256": sha(araw)},
        "provenance": {"producer": _claimed(producer), "evidence": evidence, "baseline_reproduced": verified,
                       "evaluator": "deterministic lexical checks; no model, judge or network was used"},
        "counts": counts,
        "metrics": {
            "questions": len(qs), "passed": counts["correct_supported"] + counts["correct_abstain"],
            "grounded_accuracy": _ratio(counts["correct_supported"], n_ans),
            "abstention_recall": _ratio(counts["correct_abstain"], n_un),
            "abstention_precision": _ratio(counts["correct_abstain"], len(abst)),
            "citation_validity": _ratio(sum(1 for c in cit if c["status"] in ("valid", "relocated")), len(cit)),
        },
        "results": rows, "notes": notes,
    }
    rep["status"] = "pass" if rep["metrics"]["passed"] == len(qs) else "fail"
    return (0 if rep["status"] == "pass" else 1), rep, render(rep)


CLAIM_KEYS = ("verified", "executed_here", "baseline_reproduced", "evidence")


def _claimed(producer: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The file's own producer label, with self-certifying fields moved under claimed_by_file (N10)."""
    if producer is None:
        return None
    out = {k: v for k, v in producer.items() if k not in CLAIM_KEYS}
    claims = {k: producer[k] for k in CLAIM_KEYS if k in producer}
    if claims:
        out["claimed_by_file"] = claims
    return out


def _ratio(n: int, d: int) -> Optional[str]:
    return f"{n}/{d}" if d else None


def render(rep: Dict[str, Any]) -> str:
    m, c = rep["metrics"], rep["counts"]
    lines = [f"grounded eval: {rep['status']}  ({m['passed']}/{m['questions']} questions pass)",
             f"  grounded accuracy {m['grounded_accuracy']}, abstention recall {m['abstention_recall']}, "
             f"abstention precision {m['abstention_precision']}, citation validity {m['citation_validity']}",
             "  " + ", ".join(f"{k} {v}" for k, v in c.items() if v),
             f"  evidence: {rep['provenance']['evidence']}",
             f"  evaluator: {rep['provenance']['evaluator']}"]
    for row in rep["results"]:
        if row["verdict"] not in PASSING:
            extra = ""
            if row.get("missing_facts"):
                extra = f" missing {row['missing_facts']}"
            elif row.get("support"):
                extra = f" support {row['support']}"
            bad = [x for x in row.get("citations", []) if x["status"] not in ("valid", "relocated")]
            if bad:
                extra += f" citation {bad[0]['status']}: {bad[0].get('detail', '')}"
            lines.append(f"  FAIL {row['id']}: {row['verdict']}{extra}")
    lines += [f"  note: {n}" for n in rep["notes"]]
    return "\n".join(lines) + "\n"


# -- output -------------------------------------------------------------------------------

def _fold(p: Path) -> str:
    """A resolved path in a form that compares equal on case- and normalisation-insensitive file systems."""
    return unicodedata.normalize("NFC", os.path.normcase(str(p))).casefold()


def _same_file(a: Path, b: Path) -> bool:
    try:
        sa, sb = os.stat(a), os.stat(b)
    except OSError:
        return False
    return (sa.st_dev, sa.st_ino) == (sb.st_dev, sb.st_ino)


def _check_target(out: Path, protect: List[Path], corpus_dir: Optional[Path] = None) -> Path:
    """An output never replaces an input, the journal, or anything in the snapshot folder (N5, N9). Paths are
    compared by file identity and case-folded after resolving, so SNAP/plots.md cannot reach snap/plots.md on a
    case-insensitive volume (M16 r2 R2). On a case-sensitive volume a folder that differs only in case from the
    snapshot folder is refused too (fail closed)."""
    out = Path(os.path.abspath(out))
    _need(not out.is_symlink() and (not out.exists() or out.is_file()), f"{out.name}: exists and is not a regular file")
    _need(out.parent.is_dir(), f"{out.name}: its folder does not exist")
    out = Path(os.path.realpath(out.parent)) / out.name
    for p in protect:
        rp = Path(os.path.realpath(os.path.abspath(p)))
        same = _same_file(out, p) or _fold(rp) == _fold(out)
        _need(not same, f"{out.name}: would overwrite an input")
    if corpus_dir is not None:
        c = Path(os.path.realpath(os.path.abspath(corpus_dir)))
        fc, fo = _fold(c), _fold(out)
        inside = (fo == fc or fo.startswith(fc.rstrip(os.sep) + os.sep) or _same_file(out, c)
                  or any(_same_file(d, c) for d in out.parents))
        _need(not inside, f"{out.name}: is inside the snapshot folder; write outputs elsewhere")
    return out


def _lock(fh, path: Path) -> None:
    """One run per journal: an exclusive non-blocking flock, released by the kernel if the process dies (N8)."""
    if fcntl is None:  # pragma: no cover - not POSIX
        return
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise Invalid(f"journal: {path.name} is in use by another run; wait for it to finish, then resume") from None


def _write_atomic(out: Path, data: bytes) -> None:
    tmp = out.parent / f".{out.name}.{secrets.token_hex(6)}.tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, out)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="grounded_eval.py", description="Offline grounded-answer evals over a source snapshot.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    an = sub.add_parser("answer", help="deterministic extractive baseline (no model)")
    an.add_argument("--corpus", required=True)
    an.add_argument("--questions", required=True)
    an.add_argument("--out", required=True)
    an.add_argument("--journal")
    an.add_argument("--resume", action="store_true")
    an.add_argument("--workers", type=int, default=1)
    an.add_argument("--fault-plan", help="drill: make named retrieval steps fail N times")
    an.add_argument("--min-coverage", type=float, default=0.75)
    ev = sub.add_parser("evaluate", help="grade an answers file against the snapshot")
    ev.add_argument("--corpus", required=True)
    ev.add_argument("--questions", required=True)
    ev.add_argument("--answers", required=True)
    ev.add_argument("--json", action="store_true")
    ev.add_argument("--out")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "answer":
            return run_answer(a)
        code, rep, text = run_evaluate(a)
        data = (json.dumps(rep, indent=2, sort_keys=True) + "\n").encode("utf-8")
        if a.out:
            t = _check_target(Path(a.out), [Path(a.questions), Path(a.answers)], Path(a.corpus))
            _write_atomic(t, data)
        sys.stdout.write(data.decode("utf-8") if a.json else text)
        return code
    except (Invalid, OSError, ValueError, OverflowError) as exc:
        msg = str(exc) if isinstance(exc, (Invalid, ValueError, OverflowError)) else f"file error: {exc.strerror or exc.__class__.__name__}"
        if getattr(a, "json", False):
            sys.stdout.write(json.dumps({"schema": REPORT_SCHEMA, "status": "invalid", "error": msg}, sort_keys=True) + "\n")
        else:
            sys.stdout.write(f"invalid: {msg}\nnothing written\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
