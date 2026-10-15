#!/usr/bin/env python3
"""Derive searchable public metadata from the existing employee contracts.

Run after editing a skill's identity, summary or tags. --check is used in CI.
No network access, employee additions or request data are involved.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "control-plane/skills.json"


def build():
    skills = []
    for contract_path in sorted((ROOT / "employees").glob("*/*/capability.contract.json")):
        folder = contract_path.parent
        identity = json.loads(contract_path.read_text(encoding="utf-8"))["identity"]
        plugin = json.loads((folder / "plugin.json").read_text(encoding="utf-8"))
        skill_path = folder / "SKILL.md"
        if not skill_path.is_file():
            raise ValueError(f"Missing skill: {skill_path.relative_to(ROOT)}")
        skills.append({
            "id": identity["id"], "name": identity["name"],
            "department": folder.parent.name, "summary": identity["summary"],
            "tags": sorted(set(identity.get("tags", []) + plugin.get("tags", []))),
            "path": skill_path.relative_to(ROOT).as_posix(),
        })
    ids = [skill["id"] for skill in skills]
    active = {item["id"] for item in json.loads((ROOT / "control-plane/roster.json").read_text())["capabilities"]
              if item["status"] == "active" and item["id"].startswith("solaris.")}
    if len(ids) != len(set(ids)) or set(ids) != active:
        raise ValueError("Skill IDs must match the active Solaris roster exactly")
    return {"catalog_version": 1, "skills": skills}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build(), indent=2) + "\n"
    if args.check:
        if not DESTINATION.exists() or DESTINATION.read_text(encoding="utf-8") != rendered:
            parser.exit(1, "Skill catalog is stale. Run python tools/build_skill_catalog.py\n")
        print("Skill catalog matches source contracts and active roster")
    else:
        DESTINATION.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
