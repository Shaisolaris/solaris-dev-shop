"""M02 r2 API probe (Grok self-validation): the G04 handoff imports activate() and passes a JSON intake dict.
Does activate() return a result (never raise) for the two unbounded inputs found by C06? Usage: python m02r2_api_probe.py <activate.py>"""
import importlib.util, json, sys, tempfile, traceback
from pathlib import Path
spec = importlib.util.spec_from_file_location("act", sys.argv[1]); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
T = Path(tempfile.mkdtemp(prefix="m02r2-api-")).resolve()
cases = {}
intake = json.loads('{"name": "Bad\\udcffName", "project_type": "web app"}')  # a lone surrogate is valid JSON text
cases["lone_surrogate_name_from_json"] = lambda: m.activate(str(T / "a"), intake)
(T / "b").mkdir(); (T / "b" / ".solaris-activation.json").write_text("[" * 200000)
cases["deep_journal"] = lambda: m.activate(str(T / "b"), {"name": "B"})
for k, f in cases.items():
    try:
        r = f(); print(f"{k}: returned status={r.get('status')}")
    except BaseException as e:
        print(f"{k}: RAISED {type(e).__name__}: {str(e)[:80]}  (root created: {(T / 'a').exists() if k.startswith('lone') else 'n/a'})")
