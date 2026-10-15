# Contributing

Fixes to docs, broken paths, and secret leaks are welcome. New employees go through the [new employee proposal](.github/ISSUE_TEMPLATE/new-employee.md) issue first.

Do not:

- Add passwords, API keys, tokens, or real account details
- Add employees that are not in the active roster (propose them via an issue instead)
- Add Alfred, marketplace, or patent material
- Rename a model vendor into the product or the employee

Router changes must keep the suite green:

```bash
python3 -m unittest discover -s tests -v
python3 control-plane/meta_control_plane.py self-test
```

Open an issue with the command you ran, what you expected, and what you observed. A pull request should do the same in the description.

After editing a skill identity, summary or tags, run
`python3 tools/build_skill_catalog.py` and commit the updated catalog.
CI checks source paths and roster IDs to prevent stale discovery results.

Validate `SKILL.md` discovery metadata after changing a skill:

```bash
python3 -m pip install -r requirements-dev.txt
python3 tools/validate_skill_metadata.py
```

This developer check parses YAML and checks names and descriptions for all 61
specialists plus the coordinator. Quote descriptions containing colons. Keep
descriptions within 1024 characters and use words for comparisons. Detailed
procedures belong in the body. The intake runtime remains standard-library only.
