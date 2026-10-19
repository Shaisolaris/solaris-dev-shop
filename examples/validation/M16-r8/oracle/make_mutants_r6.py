"""M16 r6 grammar mutants (Grok self-validation, my own, aimed at the G16 r6 ADDRESSED grammar). (name, old, new); each old must occur once."""
M = [
 ("pre_verb_2", 'PRE_VERB_WORDS = 8', 'PRE_VERB_WORDS = 2'),
 ("pre_verb_12", 'PRE_VERB_WORDS = 8', 'PRE_VERB_WORDS = 12'),
 ("det_off", '_DET + r"\\b" + _READER', 'r"\\b" + _READER'),
 ("qual_min2", '{1,3}" + _HEAD', '{2,3}" + _HEAD'),
 ("head_end_off", '+ r"(?=" + _SEP + r"|\\s+" + _POST_OPEN + r"\\b)(?:\\s+"', '+ r"(?:\\s+"'),
 ("post_mod_off", '(?:\\s+" + _POST_OPEN + r"\\b[^.:;,!?\\u2013\\N{EM DASH}]{0,40}?)?', ''),
 ("sep_no_comma", '_SEP = r"(?:\\s*[:;,', '_SEP = r"(?:\\s*[:;'),
 ("anchor_no_clause", 'r"(?:^\\W*|[:;,(]\\s*|\\b" + _OPENER', 'r"(?:^\\W*|\\b" + _OPENER'),
 ("opener_no_tofor", '_OPENER + r"\\s+(?:(?:to|for)\\s+)?)"', '_OPENER + r"\\s+)"'),
 ("addressed_off", '+ r"|" + ADDRESSED +', '+'),
 ("reader_no_bare_ai", '+ _HEAD + r"|chatbots?|bots?|llms?|ai)"', '+ _HEAD + r"|chatbots?|bots?|llms?)"'),
 ("sep_order_EQUIV", '_SEP = r"(?:\\s*[:;,', '_SEP = r"(?:\\s*[,;:'),
]
