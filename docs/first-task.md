# Your first task: find, route and hand off

This walkthrough uses a synthetic login regression. The router chooses a skill;
your agent must then perform the work. No account, model key or network call is
needed for the routing step.

## 1. Find the specialist

From a checkout with Python 3.10+:

```bash
python3 control-plane/meta_control_plane.py skills playwright --department quality-security
```

The results include `solaris.qa-engineer` and its source path:
`employees/quality-security/qa-engineer/SKILL.md`. Search uses the existing skill
summaries and tags; it does not infer which tools are installed on your machine.
To see every skill, omit the search terms. Use `--json` for structured results.

## 2. Route the outcome

```bash
python3 control-plane/meta_control_plane.py intake --explain "Write a test plan for the client portal login regression"
```

The packet assigns `solaris.qa-engineer`, includes `skill_path` and
`skill_source_url`, and reports `performed_work: false`. The source URL points
to the current default branch. The relative path identifies the file in your
checkout; the wheel does not install that file. For an immutable handoff,
record the checkout commit alongside your packet:

```bash
git rev-parse HEAD
```

Review the selected skill's scope, inputs and companion files before execution.
If its tools are unavailable, report that limit instead of inventing test results.

## 3. Invoke in your host agent

Open the returned file in your existing agent, or copy its entire folder into
your host's skill directory. Keep its rules and references together. Give the
agent a concrete request, for example:

> Use the QA Engineer skill at employees/quality-security/qa-engineer/SKILL.md.
> In this local demo application, produce a test plan for a login regression:
> valid credentials should reach the dashboard; invalid credentials should show
> an error; a signed-out visitor must not reach a protected page. Inspect the
> available project first. Do not invent a URL, credential, test run or result.
> Save the plan, state which checks ran, and identify remaining gaps. Ask before
> actions outside this local scope.

This is a reusable task prompt, not a claim that a particular application has
been tested. The selected skill is allowed to request missing inputs.

## 4. Inspect the deliverable

Check that the saved plan covers those three behaviors and includes paths or
run evidence for checks actually performed. Label unrun checks. Apply the
[QA loop](QA-LOOP.md) when an independent reviewer is available; if there is no
independent reviewer, disclose that limit. A router packet alone is not task
completion or evidence that a second agent reviewed the output.

## When intake should pause

```bash
python3 control-plane/meta_control_plane.py intake "There are several things here and I cannot describe any outcome"
```

This returns `clarify`, with no assignment. In 0.54, the length of this vague
request incorrectly allowed a backend assignment. The regression suite now
covers long unknown requests in English, Spanish and French, while retaining
specific supported routes and valid multi-domain requests. This is bounded
keyword routing, not general language understanding.

[Installation](install.md) · [Architecture](architecture.md) · [Benchmark limits](performance.md)
