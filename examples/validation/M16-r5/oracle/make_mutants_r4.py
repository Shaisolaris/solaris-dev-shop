"""M16 r4 mutants of the G16 r4 changes in grounded_eval.py (Grok self-validation). Exact single-occurrence anchors."""
M = [
 ("s1_count_off", "if any(b is not None and a_seq.count(b) > a_neg.count(b) for b in set(s_neg)):", "if False:"),
 ("s1_count_ge2", "a_seq.count(b) > a_neg.count(b)", "a_seq.count(b) > a_neg.count(b) + 1"),
 ("s2_end_off", '_END = r"(?=\\s*(?:[:,.;!?-]|$|(?:and|or|reading|processing|answering|who|that|which)\\b))"', '_END = r""'),
 ("s2_end_no_reading", "|(?:and|or|reading|processing|", "|(?:and|or|processing|"),
 ("s2_end_no_comma", "(?:[:,.;!?-]|$|", "(?:[:.;!?-]|$|"),
 ("s3_unanchored", 'r"|^\\W*(?:assistants?|models?)\\s*[,:]', 'r"|\\b(?:assistants?|models?)\\s*[,:]'),
 ("s3_window_1", 'r"|^\\W*(?:assistants?|models?)\\s*[,:]\\s*(?:[\\w\']+\\s+){0,6}?"', 'r"|^\\W*(?:assistants?|models?)\\s*[,:]\\s*(?:[\\w\']+\\s+){0,1}?"'),
 ("e01_off", 'r"|\\bto\\s+(?:the\\s+|any\\s+|all\\s+)?" + _BOT + r"\\b[^.:;]{0,40}:', 'r"|\\bto\\s+(?:the\\s+|any\\s+|all\\s+)?" + _BOT + r"\\b[^.:;]{0,0}:'),
 ("e01_no_any", 'r"|\\bto\\s+(?:the\\s+|any\\s+|all\\s+)?" + _BOT', 'r"|\\bto\\s+(?:the\\s+)?" + _BOT'),
 ("end_reorder_EQUIV", "|(?:and|or|reading|", "|(?:or|and|reading|"),
]
def apply(src, old, new):
    assert src.count(old) == 1, (old, src.count(old))
    return src.replace(old, new)
