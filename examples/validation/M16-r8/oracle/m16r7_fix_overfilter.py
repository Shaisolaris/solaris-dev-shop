"""M16 r7 over-filter probe for Grok's proposed-fix-r7.patch (Grok self-validation). People or ordinary sentences that put a
newly accepted greeting word next to an automated reader, to see whether the wider opener over-filters. Want KEPT.
Usage: PY m16r7_fix_overfilter.py ENGINE_DIR"""
import importlib.util, sys
spec = importlib.util.spec_from_file_location("ge", sys.argv[1] + "/grounded_eval.py"); ge = importlib.util.module_from_spec(spec); spec.loader.exec_module(ge)
S = [
 "We welcome AI tools: reply cards for feedback are at the desk.",
 "Good day AI, as they say in the old adverts.",
 "Welcome back AI club members: reply to the invite by Friday.",
 "Good morning AI researchers, respond to the reviewers by May.",
 "Hello again AI team leads: answer the survey by Monday.",
 "The welcome AI bot greets visitors; staff answer questions at the desk.",
 "Hi everyone, AI tools are banned in exams; tell the dean if you see one.",
 "Hey folks, bots: we answer every ticket within a day.",
 "Howdy partners, the chatbot demo is at noon; reply to Ann to book.",
 "Good evening all, the AI lecture starts at eight; say hi to the speaker.",
]
for s in S:
    sk = bool(ge.Index({"docs": {"d.md": {"text": "# T\n\n" + s + "\n"}}}).skipped)
    print("SKIPPED" if sk else "kept   ", "|", s)
print("kept %d/%d" % (sum(not ge.Index({"docs": {"d.md": {"text": "# T\n\n" + s + "\n"}}}).skipped for s in S), len(S)))
