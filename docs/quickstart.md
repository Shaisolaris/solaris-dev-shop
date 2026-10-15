# Quick start

You need Python 3.10+. No install step beyond the standard library.

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

For a task spanning several specialists, see the
[multi-specialist handoff](../examples/multi-domain/README.md). One accountable
lead can work with multiple supporting specialists; one packet does not mean
only one specialist can contribute.

The [latest release](https://github.com/Shaisolaris/solaris-dev-shop/releases/latest)
and `pyproject.toml` identify the current product version. Saved walkthroughs and
roadmap entries retain the versions they actually tested. Individual skill
manifests and the router's engine/schema versions have separate version numbers.
