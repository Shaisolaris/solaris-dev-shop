import importlib.util,sys
spec=importlib.util.spec_from_file_location("ge",sys.argv[1]+"/employees/engineering/llm-agent-designer/grounded_eval.py");ge=importlib.util.module_from_spec(spec);spec.loader.exec_module(ge)
for s in sys.stdin.read().strip().split("\n"):
    print(bool(ge.Index({"docs":{"d.md":{"text":"# T\n\n"+s+"\n"}}}).skipped),"|",s)
