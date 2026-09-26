# Contributing

Fixes to docs, broken paths, and secret leaks are welcome. New employees go through the [new employee proposal](.github/ISSUE_TEMPLATE/new-employee.md) issue first.

Do not:

- Add passwords, API keys, tokens, or real account details
- Add employees that are not already in this 0.53 tree (propose them via an issue instead)
- Add Alfred, marketplace, or patent material
- Rename a model vendor into the product or the employee

Router changes must keep the suite green:

```bash
python3 tests/test_router.py
python3 control-plane/meta_control_plane.py self-test
```

Open an issue with the command you ran, what you expected, and what you observed. A pull request should do the same in the description.
