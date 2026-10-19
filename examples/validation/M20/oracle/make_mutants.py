"""M20 prep: exact single-occurrence mutants of the Grok reference stub; each targets one behaviour and names the
check expected to kill it. Grok self-validation."""
import json, os, sys
here = os.path.dirname(os.path.abspath(__file__)); stubs = os.path.join(here, "..", "stubs")
src = open(os.path.join(stubs, "reference.html")).read()
M = [
 ("no_stale_guard", ["C06", "C07"], [("if (STALE === 'seq' ? my !== seq : term !== q.value.trim()) return;\n      setBusy(false); const items", "setBusy(false); const items"),
                                     ("  if (ctl) ctl.abort();\n", "\n")]),
 ("no_abort_seq_kept", [], [("  if (ctl) ctl.abort();\n", "\n")]),  # equivalent by design: seq guard alone suffices (control mutant, should survive)
 ("no_focus_restore", ["C11"], [("  if (inList) { const bs = out.querySelectorAll('button'); (bs[Math.min(idx, bs.length - 1)] || rh).focus(); }\n", "\n")]),
 ("no_live_region", ["C01", "C04"], [('<div id="status" role="status" aria-live="polite"></div>', '<div id="status"></div>')]),
 ("focus_outline_removed", ["C08"], [("</head>", "<style>button:focus,input:focus{outline:none}</style></head>")]),
 ("save_fail_rerenders", ["C09"], [(".catch(() => { say(''); al.textContent = 'Save failed. Press Save to try again.'; })",
                                   ".catch(() => { say(''); al.textContent = 'Save failed. Press Save to try again.'; render(Array.from(out.querySelectorAll('li')).map(li => ({id: li.querySelector('button').dataset.id, name: li.querySelector('span').textContent}))); document.activeElement.blur(); })")]),
 ("error_keeps_busy", ["C05"], [("      setBusy(false); say(''); al.textContent = 'Search failed.", "      say('Loading results...'); al.textContent = 'Search failed.")]),
 ("no_save_guard", ["A08"], [("if (!b || b.getAttribute('aria-disabled') === 'true') return;", "if (!b) return;")]),
 ("label_innerhtml", ["A05"], [("sp.textContent = x.name;", "sp.innerHTML = x.name;")]),
 ("fixed_width", ["C12"], [("</head>", "<style>main{width:640px}</style></head>")]),
 ("empty_not_announced", ["C04"], [("say(items.length ? items.length + ' results' : 'No results for ' + term);", "say(items.length ? items.length + ' results' : '');")]),
 ("save_success_silent", ["C10"], [("say('Saved ' + b.dataset.id); b.textContent = 'Saved';", "say('');")]),
]
os.makedirs(os.path.join(stubs, "mutants"), exist_ok=True)
plan = []
for name, kills, edits in M:
    s = src
    for a, b in edits:
        assert s.count(a) == 1, (name, a[:50], s.count(a))
        s = s.replace(a, b)
    open(os.path.join(stubs, "mutants", f"{name}.html"), "w").write(s)
    bnd = json.load(open(os.path.join(stubs, "binding-reference.json")))
    bnd["name"] = f"mutant:{name} (of Grok reference)"; bnd["page"] = {"serve_dir": "..", "path": f"mutants/{name}.html"}
    json.dump(bnd, open(os.path.join(stubs, "mutants", f"binding-{name}.json"), "w"), indent=1)
    plan.append({"mutant": name, "expected_killers": kills})
json.dump(plan, open(os.path.join(stubs, "mutants", "plan.json"), "w"), indent=1)
print(len(plan), "mutants written")
