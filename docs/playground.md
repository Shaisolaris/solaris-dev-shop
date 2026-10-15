# Try the router without installing it

Open [Try the intake router](https://github.com/Shaisolaris/solaris-dev-shop/actions/workflows/try-router.yml)
and choose **Run workflow** if you have write access. Other users can fork the
public repository and run the same workflow in their own fork. Enter a sample
task, run it, then open the completed run's Summary to see the assignment JSON.
Only include text you are comfortable putting in public Actions logs.

The workflow needs read-only repository permissions. It runs the same Python
engine as the CLI, with no provider keys, model calls, specialist execution,
messages, deployment or persistent conversation state. Input is passed through
an environment variable, not interpolated into shell source, and HTML is escaped
in the summary. This is a routing demonstration, not a hosted agent service.

For a saved example without even running Actions, see the
[multi-domain](../examples/multi-domain/README.md) and
[escalation](../examples/escalation/README.md) walkthroughs.
