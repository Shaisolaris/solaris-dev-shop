"""G16 r14 mutants: the r13 set (those whose code still exists) plus r14 content-free grammar mutants. G16 r13 mutants: the 27 M16 r12 teeth mutants plus r13 content-anywhere mutants; each edits grounded_eval.py in a temp copy and the G16 tests must fail. Usage: PY teeth.py WT [NAMES]"""
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
 # content_quote_off retired in r13: the immediate quote branch was removed as redundant with anywhere_quote
 "content_aux_noun_off": ('r"|\\s+(?:will|must|should|shall|would|can|could|may|might|is|are|was|were)\\b', 'r"|\\s+(?:zzqq)\\b'),
 "content_clause_off": ('r"|(?:(?<=say)|(?<=state)', 'r"|(?:(?<=zzqq)|(?<=zzqr)'),
 "content_wh_guard_off": ('\\s+(?!(?:when|whether|if|how|what|where|which"', '\\s+(?!(?:zzqq|whether|if|how|what|where|which"'),
 "content_msg_noun_off": ('_MSG_NOUN = (r"(?:questions?|ones?|emails?', '_MSG_NOUN = (r"(?:zzqq|ones?|emails?'),
 "content_msg_only_question": ('_MSG_NOUN = (r"(?:questions?|ones?|emails?|e-mails?|messages?|calls?|letters?|requests?|tickets?|queries|query|post|posts"', '_MSG_NOUN = (r"(?:questions?"'),
 "anywhere_that_off": ('r"|[^.!?;]*?\\bthat\\s+(?:the|a|an', 'r"|[^.!?;]*?\\bzzqq\\s+(?:the|a|an'),
 "anywhere_quote_off": ('r"|[^.!?;]*?(?:[\\"\\u201c\\u2018:]|\\s\'(?=\\w))"', 'r"|zzqq"'),
 "anywhere_yesno_off": ('r"|[^.!?;]*?\\b(?:only|always|just|simply)\\s+(?:yes|no)\\b"', 'r"|zzqq"'),
 "anywhere_clause_off": ('\\b(?:the|a|an|this|it|our|your|its|there)\\s+(?:(?!(?:that|which|who)\\b)', '\\bzzqq\\s+(?:(?!(?:that|which|who)\\b)'),
 "clause_wh_guard_off": ('r"|(?:(?!\\b(?:when|whether|if|how|what|where|which|who|why|once|until|unless|as)\\b)[^.!?;,])*?"', 'r"|(?:[^.!?;,])*?"'),
 "clause_relative_guard_off": ('(?:(?!(?:that|which|who)\\b)[\\w\'\\u2019-]+\\s+){0,3}"', '(?:[\\w\'\\u2019-]+\\s+){0,3}"'),
 "no_later_guard_off": ('(?!\\s+(?:later|sooner|more|longer|less|earlier)\\b)', ''),
 "subj_stop_no_please": ('|please|kindly|just|you|your|to"', '|kindly|just|you|your|to"'),
 "free_rest_off": ('r"(?=" + _FREE_REST + r")"', 'r""'),
 "chunk_word_boundary_off": ('(?:(?<![\\w\\u2019-])|(?=[(:]))" + _CHUNK + r"(?![\\w\\u2019-])', '" + _CHUNK + r"'),
 "adv_case_off": ('(?-i:[a-z]+ly)', '[a-z]+ly'),
 "lw_case_off": ('(?-i:[a-z0-9][a-z0-9\\u2019\'-]*)', '[\\w\\u2019\'-]+'),
 "name_after_any_prep": ('r"|inside|outside|until|till)\\s+" + _NAME', 'r"|inside|outside|until|till|first|every|each|this|next)\\s+" + _NAME'),
 # name_any_case retired: with the content-word guard on _NAME it is equivalent to _LNP after a preposition
 "name_cw_guard_off": ('_NAME = r"(?!" + _CW + r"\\b)(?-i:', '_NAME = r"(?-i:'),
 "name_long_tag": ('(?:[A-Z0-9]{1,3}|[0-9]+)\\b)?)"', '[\\w-]+)?)"'),
 "quote_noun_guard_off": ("(?!\\s+(?![\\'\\u2018\\\"\\u201c])[\\w'-]+\\s+(?:are", "(?!\\s+[\\w'-]+\\s+(?:are"),
 "cw_no_that": ('_CW = (r"(?:that|which', '_CW = (r"(?:zzqq|which'),
 "cw_no_yes_no": ('|with|yes|no|saying|stating|telling', '|with|saying|stating|telling'),
 "pronoun_obj_any": ('r"|(?:that|this|it)(?=\\s*(?:[.!?;)]|$))"', 'r"|(?:that|this|it)\\b"'),
 "second_verb_any": ('r"|(?:and|or)\\s+(?:" + _AUX + r"\\s+)?" + _SAY + r"\\b"', 'r"|(?:and|or)\\b[^.!?]*"'),
 "conj_tail_that_ok": ('(?:so|and|but|as|while|because|since)\\s+(?!that\\b)', '(?:so|and|but|as|while|because|since)\\s+'),
 "see_any_quote": ('r"|\\(\\s*see\\b[^()\\"\\u201c\\u201d:]{0,60}\\)"', 'r"|\\([^()]{0,80}\\)"'),
 "colon_see_any": ('r"|:\\s*see\\s+" + _LNP', 'r"|:\\s*" + _LNP'),
 "whose_any": ('r"(?:\\s+whose\\s+" + _CLAUSE_W', 'r"(?:\\s+(?:whose|that|who)\\s+" + _CLAUSE_W'),
 "conj_reply_word_off": ('(?![^.!?;:\\"\\u201c\\u2018]*?" + _REPLY_WORD + r")"', '"'),
 "paren_cw_off": ('r"|\\((?:\\s*(?!" + _CW + r"\\b)[^()', 'r"|\\((?:\\s*(?!zzqq\\b)[^()'),
 "elliptic_guard_off": ('r"(?!(?:asked|told|prompted|needed|possible|necessary|required|unsure)\\b)"', 'r""'),
 "wh_short_off": ('r"|(?:how|what|where|why)\\s+" + _CLAUSE_W + r"(?:\\s+" + _CLAUSE_W + r"){0,3}(?=\\s*(?:[.!?;,)]|$))"', 'r"|(?:how|what|where|why)\\s+" + _CLAUSE_W + r"(?:\\s+" + _CLAUSE_W + r"){0,8}"'),
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
