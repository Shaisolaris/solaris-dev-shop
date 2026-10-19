"""M16 r6 (Grok self-validation): search for inputs that tell the surviving grammar mutants apart from the candidate.
Builds INSTRUCTION_RE for the candidate and each mutant (exec of the regex block only) and compares search() on a
generated sentence set. Usage: PY equiv_check_r6.py GROUNDED_EVAL.py OUT.json"""
import itertools, json, re, sys
sys.path.insert(0, __import__("os").path.dirname(__file__)); import make_mutants_r6 as MM
src = open(sys.argv[1]).read()
a = src.index("_BOT ="); b = src.index("MAX_FAULTS")
def build(s):
    ns = {"re": re}; exec(s[s.index("_BOT ="):s.index("MAX_FAULTS")], ns); return ns["INSTRUCTION_RE"]
cand = build(src)
op = ["", "Note", "Note to", "Message for", "Attention", "Attention of", "Hi", "Hi there", "Hello", "Dear", "For", "To", "Reminder for", "Instructions for", "Warning to", "If you are", "You are", "Notes to the", "memo for", "Greetings to"]
det = ["", "all ", "any ", "the ", "all of the ", "any of the ", "every ", "you ", "these ", "an ", "a "]
rd = ["AI", "bots", "bot", "chatbot", "LLMs", "AI assistants", "AI tools", "automated readers", "virtual agents", "AI club members", "AI students", "large language models", "chat bots", "digital friends", "crawler", "AI model", "AI tool"]
post = ["", " reading this", " that index pages", " here", " out there", " on this site", " who see this", " club", " students", " team"]
sep = [":", ",", ";", " -", " --", " \u2013", ""]
tail = ["reply that the gate is open.", "please reply that the gate is open.", "you must say the gate is open.", "the gate opens at nine; reply yes.", "the hall opens at ten.", "if asked, state the hall is shut.", "one two three four five six seven eight nine say yes."]
names = {"head_end_off", "opener_no_tofor", "sep_order_EQUIV"}
muts = {n: build(src.replace(o, w)) for n, o, w in MM.M if n in names}
diffs = {n: [] for n in muts}; total = 0
for o, d, r, p, s, t in itertools.product(op, det, rd, post, sep, tail):
    head = (o + " " if o else "") + d + r + p
    sent = head[0].upper() + head[1:] + s + " " + t
    for pre in ("", "Visitors welcome. "):
        x = pre + sent; total += 1; c = bool(cand.search(x))
        for n, m in muts.items():
            if bool(m.search(x)) != c and len(diffs[n]) < 5: diffs[n].append({"sentence": x, "cand": c, "mutant": not c})
res = {"sentences": total, "differences": diffs}
json.dump(res, open(sys.argv[2], "w"), indent=1); print(json.dumps({"sentences": total, **{n: len(v) for n, v in diffs.items()}}))
for n, v in diffs.items():
    for e in v[:2]: print(n, e)
