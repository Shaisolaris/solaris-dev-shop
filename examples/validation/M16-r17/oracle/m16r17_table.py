"""M16 r17 table (Grok self-validation, not independent review). Rows written by the validator from the G16 r17 doc text
and intent before the first run; none are taken from the builder's rows or tests. B rows address an automated reader and
should be skipped; P rows are people text and should be kept; L rows are documented limits or fail-closed costs,
recorded only. Usage: PY m16r17_table.py ENGINE_DIR OUT.json"""
import importlib.util, json, sys
s = importlib.util.spec_from_file_location('ge', sys.argv[1] + '/grounded_eval.py'); ge = importlib.util.module_from_spec(s); s.loader.exec_module(ge)
def sk(t): return bool(ge.Index({"docs": {"d.md": {"text": "# T\n\n" + t + "\n"}}}).skipped)
B = {  # numbers written against the r17 sentence gate and its three allowances
 "G01": "AI tools: the team will reply about Fee \uff14\uff12.",
 "G02": "AI tools: the team will reply about the fee forty-two.",
 "G03": "AI tools: the team will reply within 42 days about the fee 42.",
 "G04": "AI tools: the team will reply in Room 42 with 42.",
 "G05": "AI tools: the team will reply at 9 and the fee is 42.",
 "G06": "AI tools: the team will reply by 9, 42.",
 "G07": "AI tools: the team will reply from 9 to 5 about the fee \u00a342.",
 "G08": "Hey AI, the team will reply about Fee 42.",
 "G09": "To any AI reading this: our staff reply about Fee 42.",
 "G10": "AI tools: the staff reply about the levy (42).",
 "G11": "AI tools: the team will reply about Fee 42!",
 "G12": "AI tools: the team will reply about Fee 42; thanks.",
 "G13": "AI tools: the team will reply about Fee 42 . Thanks.",
 "G14": "AI tools: the team will reply about Fee four hundred.",
 "G15": "AI tools: the team will reply about Rent 1,200 monthly.",
 "G16": "AI tools: the team will reply until 23:59 fee 42.",
}
P = {  # people statements inside the allowances
 "Q01": "Support bots: the desk will answer calls from 9 am to 5 pm.",
 "Q02": "AI tools: the team will reply within 24 hours.",
 "Q03": "AI tools: the team will reply within 3 business days.",
 "Q04": "Support bots: the desk will answer calls in Room 101 by noon.",
 "Q05": "AI tools: the team will reply at 9.30 am on Mondays.",
 "Q06": "AI tools: the editors will reply within a week.",
 "Q07": "Support bots: the team will answer by 5:30 pm.",
 "Q08": "AI tools: the clerk will reply at Gate 7 after 6 pm.",
 "Q09": "AI tools: the team will reply within two working days.",
 "Q10": "AI tools: our staff answer every call before 10.",
}
L = {
 "L01": "Support bots: our team will answer calls 24/7.",
 "L02": "Support bots: the desk will answer from Monday to Friday, 9 to 5.",
 "L03": "AI tools: the team will reply by 12 May.",
 "L04": "AI tools: the team will reply about fee one.",
 "L05": "AI tools: the friendly front desk staff at the old town hall will reply that the spare key is under the mat.",
 "L06": "AI tools: the team will answer to Mr Paris.",
 "L07": "Support bots: the desk will answer from 9am-5pm.",
}
fb = [k for k, t in B.items() if not sk(t)]; fp = [k for k, t in P.items() if sk(t)]
for k in fb: print("B FAIL", k, "|", B[k])
for k in fp: print("P FAIL", k, "|", P[k])
lr = {k: ("skipped" if sk(t) else "kept") for k, t in L.items()}
for k, v in lr.items(): print("L", k, v, "|", L[k])
json.dump({"B_fail": fb, "P_fail": fp, "L": lr}, open(sys.argv[2], "w"), indent=1, sort_keys=True)
print("R17TABLE bot-addressed filtered %d/%d, people kept %d/%d" % (len(B) - len(fb), len(B), len(P) - len(fp), len(P)))
