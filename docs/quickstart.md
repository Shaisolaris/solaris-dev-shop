# Quick start

You need Python 3. No install step beyond the standard library.

From the repository root:

```bash
python3 control-plane/meta_control_plane.py self-test
python3 control-plane/meta_control_plane.py intake "Write a test plan for the client portal login regression"
```

The first command prints `meta control-plane selftest: OK`.

The second prints JSON. For this request the decision is `assign`, the domain is `qa`, and the accountable role is `solaris.qa-engineer`. `performed_work` is `false`. The chief of staff assigned the work. It did not write the test plan.

Open the named skill:

`employees/quality-security/qa-engineer/SKILL.md`

A saved copy of one run is in `examples/route-a-task/`.
