#!/usr/bin/env python3
"""G16 r7 mutants: M16 r4's set (oracle/make_mutants_r4.py, read unchanged; anchors that r6 removed are listed as retired)
plus r6 mutants of the addressee grammar. Usage: make_mutants_r6.py <grounded_eval.py> <out> <M16 r4 make_mutants_r4.py>"""
import importlib.util, sys
from pathlib import Path
R6 = [
    ("r6_grammar_off", '    + r"|" + ADDRESSED +\n', '    + r"|QQQ" + ADDRESSED +\n'),
    ("r6_window_const_7", "PRE_VERB_WORDS = 8\n", "PRE_VERB_WORDS = 7\n"),
    ("r6_window_regex_2", 'r"(?:[\\w\']+\\s+){0," + str(PRE_VERB_WORDS) + r"}?"', 'r"(?:[\\w\']+\\s+){0," + "2" + r"}?"'),
    ("r6_no_semicolon", '_SEP = r"(?:\\s*[:;,\\u2013\\N{EM DASH}]|\\s+--?)\\s*"', '_SEP = r"(?:\\s*[:,\\u2013\\N{EM DASH}]|\\s+--?)\\s*"'),
    ("r6_no_dash", '_SEP = r"(?:\\s*[:;,\\u2013\\N{EM DASH}]|\\s+--?)\\s*"', '_SEP = r"(?:\\s*[:;,])\\s*"'),
    ("r6_no_every_each", "|every|each|all|any|", "|all|any|"),
    ("r6_no_to_for_opener", "|greetings|to|for\"", "|greetings\""),
    # the lookahead and the post-modifier group each enforce "the head ends its noun phrase"; dropping one alone is equivalent
    ("r6_head_lookahead_off_EQUIV", 'r"(?=" + _SEP + r"|\\s+" + _POST_OPEN + r"\\b)(?:\\s+"', 'r"(?:\\s+"'),
    ("r6_head_end_off", 'r"(?=" + _SEP + r"|\\s+" + _POST_OPEN + r"\\b)(?:\\s+" + _POST_OPEN + r"\\b[^',
     'r"(?:\\s+" + r"\\w+" + r"\\b[^'),
    ("r6_anchor_anywhere", 'ADDRESSED = (r"(?:^\\W*|', 'ADDRESSED = (r"(?:\\b|^\\W*|'),
    ("r6_no_comma_anchor", '|[:;,(]\\s*|\\b" + _OPENER', '|[:;(]\\s*|\\b" + _OPENER'),
    ("r6_one_qualifier", '_QUAL + r"\\s+){1,3}" + _HEAD', '_QUAL + r"\\s+){1,1}" + _HEAD'),
    ("r6_no_friend", "|programs?|friends?|bots?", "|programs?|bots?"),
    ("r6_no_bare_ai", '|chatbots?|bots?|llms?|ai)"', '|chatbots?|bots?|llms?)"'),
    ("r7_no_attention_of", "attention(?:\\s+of)?|", "attention|"),
    ("r7_no_there", "|(?:hey|hi|hello)(?:\\s+there)?|", "|hey|hi|hello|"),
    ("r7_there_required", "(?:hey|hi|hello)(?:\\s+there)?|", "(?:hey|hi|hello)\\s+there|"),
    ("r7_of_required", "attention(?:\\s+of)?|", "attention\\s+of|"),
    ("r7_there_any_word", "(?:hey|hi|hello)(?:\\s+there)?|", "(?:hey|hi|hello)(?:\\s+\\w+)?|"),
]
src = Path(sys.argv[1]).read_text(); out = Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("m16r4", sys.argv[3]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
for name, old, new in list(m.M) + R6:
    if src.count(old) != 1:
        print(f"RETIRED {name}: anchor count {src.count(old)} on r6 (the code it mutated was replaced)"); continue
    d = out / name; d.mkdir(parents=True, exist_ok=True); (d / "grounded_eval.py").write_text(src.replace(old, new))
    print(name)
