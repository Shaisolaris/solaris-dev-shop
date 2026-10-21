"""M16 r12 teeth (Grok self-validation, not independent review): the builder's 26 G16 r12 mutants copied unchanged plus validator mutant content_msg_only_question. Original header: G16 r12 mutants: the 19 M16 r11 teeth mutants plus r12 content-rule mutants; each edits grounded_eval.py in a temp copy and the G16 tests must fail. Usage: PY teeth.py WT [NAMES]"""
import os, shutil, subprocess, sys, tempfile
WT = sys.argv[1]; F = "employees/engineering/llm-agent-designer/grounded_eval.py"
M = {
 "subj_stop_off": ('_SUBJ_WORD = r"(?!" + _SUBJ_STOP + r"\\b)[\\w\'-]+"', '_SUBJ_WORD = r"[\\w\'-]+"'),
 "later_say_off": ('r"(?![^.!?]*?(?:[,:;', 'r"(?!zzqq[^.!?]*?(?:[,:;'),
 "later_say_no_adverbs": ('(?:(?:so|and|but|please|now|then|just|simply|always|only)\\s+){0,2}"', '"'),
 "strict_tail_off": ('_FREE_TAIL = _tail(_SAY_STRICT)', '_FREE_TAIL = _tail(_SAY_VERB)'),
 "strict_say_any": ('r"|(?:say|state)\\b(?=', 'r"|(?:say|state)\\b(?=|'),
 "reply_noun_off": ('r"(?!\\s+" + _REPLY_NOUN + r"\\b)"', 'r""'),
 "crawler_qual_off": ('|(?:(?:search|web|site)\\s+)?crawlers?|', '|crawlers?|'),
 "gap_colon_off": ('(?:[\\w\']+[,:]?\\s+){0,"', '(?:[\\w\']+,?\\s+){0,"'),
 "asker_adj_off": ('|other|new|incoming)\\s+){0,2}"', '|other|new|incoming)\\s+){0,1}"'),
 "subj_stop_no_you": ('|please|kindly|just|you|your|to"', '|please|kindly|just|your|to"'),
 "strict_tell_any": ('r"|tell\\b(?=\\s+(?:(?:', 'r"|tell\\b(?=|\\s+(?:(?:'),
 "subj_aux_off": ('|will|shall|would|can|could|may|might|must|should|do|does|did|usually|often|also|still|normally)")', ')")'),
 "subj_head_off": ('_SUBJ_LAST = r"(?!(?:" + _SUBJ_STOP + r"|" + _SUBJ_HEAD_STOP + r")\\b)', '_SUBJ_LAST = r"(?!(?:" + _SUBJ_STOP + r")\\b)'),
 "it_subject_back": ('_SUBJECT = (r"(?:(?:we|they|i|he|she|staff|', '_SUBJECT = (r"(?:(?:we|they|i|he|she|it|staff|'),
 "tell_them_back": ('|(?:the\\s+)?(?:users?|people|everyone|anyone|visitors?', '|(?:the\\s+)?(?:users?|people|everyone|anyone|them|visitors?'),
 "gerund_off": ('r"|(?:replying|responding|answering|saying|stating)\\s+that', 'r"|(?:zzqq)\\s+that'),
 "gerund_noun_guard_off": ('that\\b(?!\\s+(?:questions?|ones?"', 'that\\b(?!\\s+(?:zzqq|ones?"'),
 "subj_head_no_model": ('|tools?|assistants?|models?|agents?', '|tools?|assistants?|agents?'),
 "content_off": ('r"(?!" + _CONTENT + r")"\n', 'r""\n'),
 "content_that_off": ('|\\s+that\\s+(?!" + _MSG_NOUN', '|\\s+zzqq\\s+(?!" + _MSG_NOUN'),
 "content_quote_off": ('_CONTENT = (r"\\s*[\\"\'\\u201c\\u2018:]|', '_CONTENT = (r"\\s*zzqq|'),
 "content_aux_noun_off": ('r"|\\s+(?:will|must|should|shall|would|can|could|may|might|is|are|was|were)\\b', 'r"|\\s+(?:zzqq)\\b'),
 "content_clause_off": ('r"|(?:(?<=say)|(?<=state)', 'r"|(?:(?<=zzqq)|(?<=zzqr)'),
 "content_wh_guard_off": ('\\s+(?!(?:when|whether|if|how|what|where|which"', '\\s+(?!(?:zzqq|whether|if|how|what|where|which"'),
 "content_msg_noun_off": ('_MSG_NOUN = (r"(?:questions?|ones?|emails?', '_MSG_NOUN = (r"(?:zzqq|ones?|emails?'),
 "content_msg_only_question": ('_MSG_NOUN = (r"(?:questions?|ones?|emails?|e-mails?|messages?|calls?|letters?|requests?|tickets?|queries|query|post|posts"', '_MSG_NOUN = (r"(?:questions?"'),
 "subj_stop_no_please": ('|please|kindly|just|you|your|to"', '|kindly|just|you|your|to"'),
}
src = open(os.path.join(WT, F)).read()
only = sys.argv[2:]
for name, (a, b) in M.items():
    if only and name not in only: continue
    if src.count(a) != 1:
        print("MUTANT-NOT-APPLIED", name, src.count(a)); continue
    t = tempfile.mkdtemp(prefix="g16t10-"); d = os.path.join(t, "r")
    shutil.copytree(WT, d, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    open(os.path.join(d, F), "w").write(src.replace(a, b))
    r = subprocess.run([sys.executable, "-m", "unittest", "tests.test_g16_capability"], cwd=d, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    tail = (r.stderr.strip().splitlines() or ["?"])[-1]
    print("KILLED " if r.returncode else "SURVIVED", name, "|", tail); shutil.rmtree(t)
