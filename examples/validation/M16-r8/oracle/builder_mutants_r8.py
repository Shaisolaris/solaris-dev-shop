"""G16 r8 mutants of the greeting grammar (Grok builder teeth check). Usage: PY mutants_r8.py TREE OUTDIR
Each mutant is one text edit of grounded_eval.py; the G16 test module and r8_table.py are run against it."""
import os, shutil, subprocess, sys
tree, out = sys.argv[1], sys.argv[2]
src = open(os.path.join(tree, "employees/engineering/llm-agent-designer/grounded_eval.py"), encoding="utf-8").read()
FILL = r"""(?:\s+(?:there|again|everyone|everybody|all|folks|team|y['\u2019]all|you\s+all|once\s+more))*"""
M = {
 "fill_there_only": (FILL, r"(?:\s+there)?"),
 "fill_single": (FILL, FILL[:-1] + "?"),
 "fill_no_yall": (r"|y['\u2019]all", ""),
 "fill_no_once_more": (r"|once\s+more))*", "))*"),
 "greet_start_off": (r"""(?:(?:^\W*|[:;,(]\s*)(?:" + _GREET_START + r"\s+)?""", r"""(?:(?:^\W*|[:;,(]\s*)"""),
 "greet_start_only_sentence_start": (r"""(?:(?:^\W*|[:;,(]\s*)(?:" + _GREET_START + r"\s+)?""", r"""(?:^\W*(?:" + _GREET_START + r"\s+)?|[:;,(]\s*"""),
 "greet_start_anywhere": (r"""|(?:hey|hi|hello|greetings)" + _GREET_FILL""", r"""|(?:hey|hi|hello|greetings)" + _GREET_FILL + r"|" + _GREET_START"""),
 "greetings_no_fill": ('(?:hey|hi|hello|greetings)" + _GREET_FILL + r"|to|for"', '(?:hey|hi|hello)" + _GREET_FILL + r"|greetings|to|for"'),
 "bot_role_off": (r"""|(?:" + _BOT_ROLE + r"\s+)?(?:chatbots?|bots?)""", r"""|chatbots?|bots?"""),
 "bot_role_any_word": (r"""|(?:" + _BOT_ROLE + r"\s+)?(?:chatbots?|bots?)""", r"""|(?:[a-z][\w'-]*\s+)?(?:chatbots?|bots?)"""),
 "no_good_afternoon": ("good\\s+(?:morning|afternoon|evening)", "good\\s+(?:morning|evening)"),
 "no_yo": ("hiya|howdy|yo|", "hiya|howdy|"),
}
os.makedirs(out, exist_ok=True)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
for name, (a, b) in M.items():
    if src.count(a) != 1:
        print(name, "ANCHOR-NOT-FOUND", src.count(a)); continue
    d = os.path.join("/tmp/g16r8/mut", name); shutil.rmtree(d, ignore_errors=True); shutil.copytree(tree, d, ignore=shutil.ignore_patterns(".git"))
    open(os.path.join(d, "employees/engineering/llm-agent-designer/grounded_eval.py"), "w", encoding="utf-8").write(src.replace(a, b))
    t = subprocess.run([sys.executable, "-m", "unittest", "tests.test_g16_capability"], cwd=d, env=env, capture_output=True, text=True)
    r = subprocess.run([sys.executable, "/tmp/g16r8/scripts/r8_table.py", os.path.join(d, "employees/engineering/llm-agent-designer")], env=env, capture_output=True, text=True)
    open(os.path.join(out, name + ".txt"), "w").write(t.stderr[-3000:] + "\n--- r8_table\n" + r.stdout)
    print("%-32s tests %-7s r8_table %s" % (name, "KILLED" if t.returncode else "SURVIVED", "KILLED" if r.returncode else "SURVIVED"))
    shutil.rmtree(d)
