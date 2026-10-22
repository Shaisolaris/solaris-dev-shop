# Routing patterns

The executable router is `control-plane/meta_control_plane.py`, relative to the
installed plugin root. That is the directory containing `control-plane/`,
`chief-of-staff/` and `employees/`; it is different from a specialist's folder
or the client project being routed.

From the plugin root:

```sh
python3 control-plane/meta_control_plane.py intake "review this code" --json
python3 control-plane/meta_control_plane.py self-test
```

From another working directory, resolve the engine's absolute path inside the
installed plugin and use that path. The native chief-of-staff entry links to it.

These examples come from the current routing probes:

| Request | Primary capability |
|---|---|
| "review this code" | `solaris.code-reviewer` |
| "Design a REST API with FastAPI, JWT auth, and Postgres" | `solaris.backend-developer` |
| "Build an MVP prototype, scaffold the full-stack project end to end" | `solaris.full-stack-developer` |
| "Our pods are CrashLoopBackOff, fix the probes and HPA config" | `solaris.kubernetes-specialist` |

The router emits a bounded assignment or an escalation; it does not execute a
specialist, grant tools or authorize deployment or spending. The host supplies
execution tools and enforces its permissions.

[Policy](../../control-plane/policy.json) governs the decision. The complete
expected examples live in [routing probes](../../control-plane/routing-probes.md),
which [the routing regression suite](../../tests/test_router.py) executes.
