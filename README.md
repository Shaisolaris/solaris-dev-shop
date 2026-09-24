# Solaris Dev Shop

61 employees and one chief of staff. Free. Version 0.52. MIT.

You send a task. The chief of staff assigns one specialist. That specialist does the work. You still decide.

This is a skill library, not an app and not a marketplace. It is the V5.2.2 workforce, copied so you can read a role, copy one skill, and route one task.

## Try it

From this folder:

```bash
python3 control-plane/meta_control_plane.py intake "Write a test plan for the client portal login regression"
```

That command assigns `solaris.qa-engineer`. It does not write the test plan. The saved run is in [`examples/route-a-task/`](examples/route-a-task/). The skill is [`employees/quality-security/qa-engineer/SKILL.md`](employees/quality-security/qa-engineer/SKILL.md).

## The library

All 61 names: [`docs/employees.md`](docs/employees.md).

How to copy a skill: [`docs/install.md`](docs/install.md). How a request moves: [`docs/architecture.md`](docs/architecture.md).

![You ask. The chief of staff assigns. A specialist does the work.](assets/social-preview.png)

## What this is not

- Not 73, 58, 52, or 100 employees. The count is 61 directories.
- Not the newer Solaris work. This is the public edition of V5.2.2.
- Not Alfred, a marketplace, or a patent filing.
- Not a place to paste passwords, API keys, or tokens.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).
