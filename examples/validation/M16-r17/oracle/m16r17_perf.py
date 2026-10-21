"""M16 r17 timing probe (Grok): the r17 gate runs a second pattern over every sentence; long adversarial sentences must
classify quickly. Usage: PY m16r17_perf.py ENGINE_DIR. Prints seconds per case and PERF OK if all are under 2 s."""
import importlib.util, sys, time
s = importlib.util.spec_from_file_location('ge', sys.argv[1] + '/grounded_eval.py'); ge = importlib.util.module_from_spec(s); s.loader.exec_module(ge)
C = {
 "many_headings": "AI tools: " * 400 + "the team will reply.",
 "long_gap": "AI tools: " + "the team " * 2000 + "will reply about Fee 42.",
 "many_numbers": "AI tools: the team will reply " + "by 9 " * 2000 + ".",
 "comma_chain": "AI tools, " * 300 + "staff, " * 300 + "reply by noon.",
 "no_end": "Support bots: the desk will answer " + "within 2 days and " * 1500,
}
worst = 0
for k, t in C.items():
    t0 = time.time(); r = bool(ge.INSTRUCTION_RE.search(t)); d = time.time() - t0; worst = max(worst, d)
    print("%-14s %6.3fs skipped=%s len=%d" % (k, d, r, len(t)))
print("PERF", "OK" if worst < 2 else "SLOW", "worst %.3fs" % worst)
