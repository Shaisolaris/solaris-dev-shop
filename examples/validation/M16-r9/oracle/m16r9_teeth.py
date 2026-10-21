"""M16 r9 teeth (Grok self-validation): the builder's 9 G16 r9 mutants copied unchanged plus validator mutant subject_det_off. Original header: G16 r9 mutants: each mutant edits grounded_eval.py in a fresh clone; G16 tests must fail. Usage: PY teeth.py WT"""
import os, re, shutil, subprocess, sys, tempfile
WT = sys.argv[1]; F = "employees/engineering/llm-agent-designer/grounded_eval.py"
M = {
 "no_statement_check": ('+ _SEP + r"(?!" + _STATEMENT + r")', '+ _SEP + r"'),
 "no_free_lead": ('             + r"|(?:^\\W*|[:;(]\\s*)" + _FREE_LEAD + _STRONG + _AFTER + _TAIL + r")")', '             + r")")'),
 "no_after": ('_AFTER = r"(?:\\s+(?:everyone', '_AFTER = r"(?:\\s+(?:zzqq'),
 "no_crawler": ('|crawlers?|llms?|ai)"', '|llms?|ai)"'),
 "noun_rule_off": ('(?!\\s+[\\w\'-]+\\s+(?:are|is|was|were|will|have|has|had)\\b)"', '"'),
 "lead_stop_off": ('_FREE_LEAD = r"(?:(?!" + _LEAD_STOP + r"\\b)', '_FREE_LEAD = r"(?:'),
 "strong_any_bots": ('|chatbots?|bot|llms?|ai)")', '|chatbots?|bots?|llms?|ai)")'),
 "pronoun_gap_off": ('(?:we|they|i|he|she|it|staff|people)\\s+(?:" + _AUX', '(?:zzqq)\\s+(?:" + _AUX'),
 "subject_det_off": ('colleagues)\\b|(?:the|our|', 'colleagues)\\b|(?:zzqq|'),
 "greet_list_r8": ('|hi-ya|heya|hey-?ho|heyo|howdy|yo|hullo|hallo|sup|', '|howdy|yo|'),
}
src = open(os.path.join(WT, F)).read()
for name, (a, b) in M.items():
    if src.count(a) != 1:
        print("MUTANT-NOT-APPLIED", name, src.count(a)); continue
    t = tempfile.mkdtemp(prefix="g16t-"); d = os.path.join(t, "r")
    shutil.copytree(WT, d, ignore=shutil.ignore_patterns(".git", "__pycache__"))
    open(os.path.join(d, F), "w").write(src.replace(a, b))
    r = subprocess.run([sys.executable, "-m", "unittest", "tests.test_g16_capability"], cwd=d, capture_output=True, text=True,
                       env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    tail = (r.stderr.strip().splitlines() or ["?"])[-1]
    print("KILLED " if r.returncode else "SURVIVED", name, "|", tail)
    shutil.rmtree(t)
