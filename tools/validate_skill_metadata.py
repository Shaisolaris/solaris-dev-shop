#!/usr/bin/env python3
"""Validate top-level discovery metadata against the Agent Skills format.

Developer check only: install requirements-dev.txt. The intake runtime remains
stdlib-only. Reference: https://agentskills.io/specification
"""
import argparse
import json
from pathlib import Path
import re
import sys

import yaml

ROOT = Path(__file__).resolve().parents[1]


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ValueError(f"Duplicate metadata key: {key}")
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def validate(path):
    text = path.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", text, re.S)
    if not match:
        raise ValueError("Missing YAML frontmatter")
    data = yaml.load(match[1], Loader=UniqueKeyLoader)
    if not isinstance(data, dict):
        raise ValueError("Metadata must be a mapping")
    name, description = data.get("name"), data.get("description")
    if (not isinstance(name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            or len(name) > 64 or name != path.parent.name):
        raise ValueError("Name must match its folder and use 1-64 lowercase letters, digits or hyphens")
    if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
        raise ValueError("Description must be a nonempty string of at most 1024 characters")
    # Compatibility with the skill-creator authoring validator as well as YAML.
    if "<" in description or ">" in description:
        raise ValueError("Use words or Unicode arrows instead of angle brackets in discovery metadata")
    compatibility = data.get("compatibility")
    if compatibility is not None and (not isinstance(compatibility, str) or not 1 <= len(compatibility) <= 500):
        raise ValueError("Compatibility must be a string of 1-500 characters")
    metadata = data.get("metadata")
    if metadata is not None and (not isinstance(metadata, dict)
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in metadata.items())):
        raise ValueError("Optional metadata must map strings to strings")
    return {"path": path.relative_to(ROOT).as_posix(), "name": name, "description_chars": len(description)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    paths = sorted((ROOT / "employees").glob("*/*/SKILL.md")) + [ROOT / "chief-of-staff/SKILL.md"]
    passed, failures = [], []
    for path in paths:
        try:
            passed.append(validate(path))
        except (OSError, ValueError, yaml.YAMLError, TypeError) as error:
            failures.append({"path": path.relative_to(ROOT).as_posix(), "error": str(error)})
    report = {"entrypoints": len(paths), "passed": len(passed), "failures": failures}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Skill metadata: {len(passed)}/{len(paths)} entrypoints valid")
        for failure in failures:
            print(f"{failure['path']}: {failure['error']}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
