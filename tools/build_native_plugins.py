#!/usr/bin/env python3
"""Build native source plugins from one immutable Git revision. Does not install or publish.

Requires PyYAML in the build environment. Plugin runtime files retain the canonical
repository layout; skills/ contains discovery adapters, not extra capabilities.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/Shaisolaris/solaris-dev-shop"
SDK_VERSION = "2.1.2"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build(revision, destination):
    commit = git("rev-parse", "--verify", revision + "^{commit}").decode().strip()
    destination = Path(destination).resolve()
    if os.path.commonpath([str(ROOT), str(destination)]) == str(ROOT):
        raise ValueError("output must be outside the source checkout")
    if destination.exists():
        raise ValueError("output already exists; use a fresh owned directory")
    source = {}
    for row in git("ls-tree", "-rz", commit).split(b"\0"):
        if not row:
            continue
        header, name = row.split(b"\t", 1)
        mode, kind, obj = header.decode().split()
        path = name.decode("utf-8")
        if mode not in ("100644", "100755") or kind != "blob":
            raise ValueError("non-regular source entry: " + path)
        if Path(path).is_absolute() or ".." in Path(path).parts:
            raise ValueError("unsafe source path: " + path)
        source[path] = (git("cat-file", "blob", obj), mode)
    version_text = source["pyproject.toml"][0].decode()
    version = re.search(r'(?m)^version\s*=\s*"([0-9]+\.[0-9]+(?:\.[0-9]+)?)"', version_text).group(1)
    plugin_version = version if version.count(".") == 2 else version + ".0"
    role_paths = sorted(p for p in source if re.fullmatch(r"employees/[^/]+/[^/]+/SKILL.md", p))
    if len(role_paths) != 61:
        raise ValueError("expected the original 61 employee roles")
    skills = []
    for path in ["chief-of-staff/SKILL.md"] + role_paths:
        text = source[path][0].decode("utf-8")
        if not text.startswith("---\n"):
            raise ValueError("missing frontmatter: " + path)
        metadata = yaml.safe_load(text.split("---", 2)[1])
        name, description = metadata["name"], metadata["description"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) >= 64:
            raise ValueError("invalid skill name: " + str(name))
        if not isinstance(description, str) or not description.strip():
            raise ValueError("empty description: " + path)
        skills.append({"name": name, "description": description, "canonical": path})
    if len({s["name"] for s in skills}) != len(skills):
        raise ValueError("duplicate discovery names")
    canonical_manifest = {p: hashlib.sha256(data).hexdigest() for p, (data, _) in source.items()}
    identity = {"name": "solaris-dev-shop", "version": plugin_version,
                "description": "61 specialist workflows, a chief of staff and deterministic local helpers.",
                "author": {"name": "Solaris Technologies", "email": "shehryar@solaristek.com",
                           "url": "https://solaristek.com"},
                "homepage": REPOSITORY, "repository": REPOSITORY, "license": "MIT"}
    destination.mkdir(parents=True)
    for host in ("openai", "claude", "opencode-v2"):
        target = destination / host / "solaris-dev-shop"
        target.mkdir(parents=True)
        for path, (data, mode) in source.items():
            f = target / path
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(data)
            f.chmod(0o755 if mode == "100755" else 0o644)
        for skill in skills:
            folder = target / "skills" / skill["name"]
            folder.mkdir(parents=True)
            frontmatter = yaml.safe_dump({"name": skill["name"], "description": skill["description"]},
                                        sort_keys=False, allow_unicode=True).strip()
            canonical = "../../" + skill["canonical"]
            body = ("---\n" + frontmatter + "\n---\n\n"
                    "Load the canonical Solaris workflow at [" + skill["name"] + "](" + canonical + "). "
                    "Resolve that path relative to this SKILL.md, then use its instructions and companion files. "
                    "Run helpers from their canonical role folder so shared imports and resource paths remain valid. "
                    "The host supplies execution tools and permissions; this adapter adds no grants or background jobs.\n")
            (folder / "SKILL.md").write_text(body, encoding="utf-8")
        if host == "openai":
            write_json(target / "plugin.json", dict(identity,
                **{"$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                   "extensions": {"com.openai": {"requires_local_executor": True,
                       "interface": {"displayName": "Solaris Dev Shop",
                           "shortDescription": "Specialist workflows with executable local tools",
                           "longDescription": "61 specialist workflows and a chief of staff, backed by local tools for recoverable delivery, reconciled data, API behavior and evidence checks. Workflows use the host tools and permissions and retain their documented runtime limits.",
                           "developerName": "Solaris Technologies", "category": "Productivity",
                           "websiteURL": REPOSITORY, "supportURL": REPOSITORY + "/issues",
                           "defaultPrompt": ["Route a code review to the appropriate Solaris specialists.",
                                             "Run the local interrupted-delivery and recovery demonstration.",
                                             "Check the saved evidence before accepting this delivery."]}}}}))
        elif host == "claude":
            write_json(target / ".claude-plugin/plugin.json", identity)
        else:
            write_json(target / "package.json", {"name": "solaris-dev-shop-opencode", "version": plugin_version,
                "type": "module", "license": "MIT", "repository": REPOSITORY,
                "exports": {".": "./native/opencode.mjs"},
                "dependencies": {"@opencode/plugin": SDK_VERSION}})
            write_json(target / "native/skills.json", skills)
            (target / "server.mjs").write_text('export { default } from "./native/opencode.mjs";\n', encoding="utf-8")
            (target / "native/opencode.mjs").write_text('''import { Plugin } from "@opencode/plugin";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
const root = new URL("../", import.meta.url);
export default Plugin.define({
  id: "solaris.dev-shop",
  async setup(ctx) {
    const index = JSON.parse(await readFile(new URL("native/skills.json", root), "utf8"));
    const skills = await Promise.all(index.map(async (skill) => {
      const path = fileURLToPath(new URL(skill.canonical, root));
      return { id: "solaris." + skill.name, name: skill.name,
        description: skill.description, path, content: await readFile(path, "utf8") };
    }));
    await ctx.skill.transform((editor) => { for (const skill of skills) editor.add(skill); });
  },
});
''', encoding="utf-8")
        (target / "NATIVE-INSTALL.md").write_text(
            "# Solaris Dev Shop native plugin\n\n"
            "Publisher: Solaris Technologies. Source release: " + version + " (`" + commit + "`).\n\n"
            "This is a source plugin using the host native plugin format. It contains the canonical specialist workflows and local helpers, plus discovery wiring. It adds no account access, telemetry backend, standing tool grants or background jobs.\n\n"
            "OpenAI/Codex: install through a local plugin marketplace for testing; directory submission uses the ZIP. Desktop execution is required for the local helpers.\n\n"
            "Claude Code: register the supplied marketplace, then run `/plugin install solaris-dev-shop@solaris-native-validation-062`. A public marketplace URL will replace the test source before distribution.\n\n"
            "OpenCode V2: add the extracted plugin directory to `plugins` in opencode.json. Registry/Git package installation is a separate distribution step. V1 plugin APIs are not supported by this V2 adapter.\n\n"
            "Run helpers from canonical role folders; use README.md and docs/capabilities.md for actual commands and limits. The router wheel is optional and does not contain all specialist resources.\n\n"
            "Native host loading and helper execution are tested separately from model-driven activation. Local installation is not official marketplace approval.\n", encoding="utf-8")
        # npm always drops .gitignore; it is repository configuration, not a runtime resource.
        shipped_manifest = dict(canonical_manifest)
        omitted = []
        if host == "opencode-v2" and ".gitignore" in shipped_manifest:
            del shipped_manifest[".gitignore"]
            omitted.append(".gitignore")
        write_json(target / "SOLARIS-BUILD-SOURCE.json", {"source_commit": commit,
            "source_repository": REPOSITORY, "source_version": version, "native_version": plugin_version,
            "host": host, "employee_roles": 61, "coordinators": 1, "discovery_adapters": 62,
            "canonical_files": shipped_manifest, "omitted_repository_config": omitted,
            "official_listing_approved": False,
            "limits": "Candidate packaging only. Host discovery and runtime outcomes require separate tests. No provider approval or model execution is implied."})
        with zipfile.ZipFile(destination / (host + "-solaris-dev-shop.zip"), "w", zipfile.ZIP_DEFLATED) as archive:
            for f in sorted(target.rglob("*")):
                if f.is_file():
                    archive.write(f, f.relative_to(target))
    write_json(destination / "BUILD.json", {"source_commit": commit, "source_version": version,
        "plugin_version": plugin_version, "hosts": ["openai", "claude", "opencode-v2"],
        "canonical_source_files": len(source), "employee_roles": 61, "coordinators": 1,
        "new_capabilities_from_adapters": 0, "published": False})
    return commit


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        print(build(args.revision, args.output))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, str(error) + "\n")
