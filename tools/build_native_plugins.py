#!/usr/bin/env python3
"""Build one native source plugin for Codex, Claude Code and OpenCode V2.

Canonical implementation bytes come only from an immutable Git revision.
Requires PyYAML. Does not install, register, submit or publish anything.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "https://github.com/Shaisolaris/solaris-dev-shop"
DISTRIBUTION = "https://github.com/Shaisolaris/solaris-dev-shop-plugins"
MARKETPLACE = "solaris-technologies"
SDK_VERSION = "2.1.2"


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def native_readme(version, commit):
    return f"""# Solaris Dev Shop native plugin

61 specialist workflows, a chief of staff and executable local helpers. Published by
Solaris Technologies. Generated from [Solaris Dev Shop {version}]({REPOSITORY}/tree/{commit}).

## Install

### Codex

```sh
codex plugin marketplace add Shaisolaris/solaris-dev-shop-plugins
codex plugin add solaris-dev-shop@{MARKETPLACE}
```

### Claude Code

```text
/plugin install solaris-dev-shop --marketplace Shaisolaris/solaris-dev-shop-plugins
```

Or add this repository as a marketplace and install `solaris-dev-shop@{MARKETPLACE}`.

### OpenCode V2

```sh
opencode plugin add 'github:Shaisolaris/solaris-dev-shop-plugins#main::path:plugin'
```

For a pinned installation, replace `main` with the complete distribution commit.
For a local installation, add the extracted `plugin` directory to `plugins` in
`opencode.json`. This adapter uses the V2 API, tested with CLI/SDK {SDK_VERSION}.

## Use

Ask the host to use the Solaris chief of staff or a named specialist. The native
skill entry loads the canonical workflow and its companion files. Run helpers
from their canonical role folders. See [the capability guide](docs/capabilities.md)
for runnable examples, and [the unchanged upstream README](SOURCE-README.md).

The source package contains specialist resources. The optional Python wheel
contains the deterministic router and catalog rather than every helper.

## Scope and evidence

The plugin adds no account access, standing tool permissions, telemetry service,
MCP connection or background schedule. The host supplies tools and permissions.
Local helpers retain their documented runtime and operating-system limits.

The 61-role roster is not evidence that every role gained new executable behavior:
the 0.62 programme records changed-role source/runtime evidence for 37 roles.
Examples are bounded local or synthetic workflows, not production certification.
Host discovery and installed-helper execution are checked separately from model
activation. Native format support is separate from curated directory approval.

OpenCode's model/provider configuration is independent of the plugin. No
standalone DeepSeek plugin marketplace approval is claimed.

## Support

Use [GitHub issues]({DISTRIBUTION}/issues) or email shehryar@solaristek.com.
Do not post credentials, personal data or private source code in public issues.
The software is distributed under the upstream [MIT license](LICENSE).
See [plugin data handling](DATA-HANDLING.md) for local files, host/provider
processing and support contacts. The publisher website policy has its own stated scope.
"""


def build(revision, destination):
    commit = git("rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode().strip()
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
    match = re.search(r'(?m)^version\s*=\s*"([0-9]+\.[0-9]+(?:\.[0-9]+)?)"', source["pyproject.toml"][0].decode())
    if match is None:
        raise ValueError("missing numeric source version")
    version = match.group(1)
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
    icon = (ROOT / "tools/native-plugin-assets/icon.png").read_bytes()
    if icon[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("icon must be a PNG")
    width, height = struct.unpack(">II", icon[16:24])
    if width != height or not 512 <= width <= 2048 or len(icon) >= 2 * 1024 * 1024:
        raise ValueError("icon must be square, 512-2048 px and under 2 MiB")
    target = destination / "plugin"
    target.mkdir(parents=True)
    canonical_manifest = {}
    relocation = {"README.md": "SOURCE-README.md"}
    for path, (data, mode) in source.items():
        if path == ".gitignore":
            continue  # repository configuration, omitted consistently by npm as well
        name = relocation.get(path, path)
        file = target / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(data)
        file.chmod(0o755 if mode == "100755" else 0o644)
        canonical_manifest[name] = digest(data)
    for skill in skills:
        folder = target / "skills" / skill["name"]
        folder.mkdir(parents=True)
        frontmatter = yaml.safe_dump({"name": skill["name"], "description": skill["description"]}, sort_keys=False, allow_unicode=True).strip()
        canonical = "../../" + skill["canonical"]
        (folder / "SKILL.md").write_text(
            "---\n" + frontmatter + "\n---\n\n"
            "Load the canonical Solaris workflow at [" + skill["name"] + "](" + canonical + "). "
            "Resolve that path relative to this SKILL.md, then use its instructions and companion files. "
            "Run helpers from their canonical role folder so shared imports and resources remain valid. "
            "The host supplies execution tools and permissions; this adapter adds no grants or background jobs.\n", encoding="utf-8")
    identity = {"name": "solaris-dev-shop", "version": plugin_version,
                "description": "61 specialist workflows, a chief of staff and executable local helpers.",
                "author": {"name": "Solaris Technologies", "email": "shehryar@solaristek.com", "url": "https://solaristek.com"},
                "homepage": DISTRIBUTION, "repository": DISTRIBUTION, "license": "MIT"}
    icon_path = "./assets/native-plugin-icon.png"
    (target / "assets/native-plugin-icon.png").write_bytes(icon)
    (target / "DATA-HANDLING.md").write_bytes((ROOT / "tools/native-plugin-assets/DATA-HANDLING.md").read_bytes())
    write_json(target / "plugin.json", dict(identity, **{
        "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
        "extensions": {"com.openai": {
            "requires_local_executor": True,
            "onboardingSkill": "./skills/chief-of-staff/SKILL.md",
            "interface": {
                "displayName": "Solaris Dev Shop",
                "shortDescription": "Specialist workflows with executable local tools",
                "longDescription": "61 specialist workflows and a chief of staff, backed by local tools for recoverable delivery, reconciled data, API behavior and evidence checks. Host tools and permissions apply; helpers retain documented runtime limits.",
                "developerName": "Solaris Technologies", "category": "Productivity",
                "websiteURL": DISTRIBUTION, "supportURL": DISTRIBUTION + "/issues",
                "privacyPolicyURL": "https://www.solaristek.com/privacy-policy/",
                "composerIcon": icon_path, "composerIconDark": icon_path,
                "logo": icon_path, "logoDark": icon_path,
                "defaultPrompt": ["Route a code review to the appropriate Solaris specialists.",
                                  "Run the local interrupted-delivery and recovery demonstration.",
                                  "Check the saved evidence before accepting this delivery."]}}}}))
    write_json(target / ".claude-plugin/plugin.json", dict(identity, icon=icon_path))
    write_json(target / "package.json", {
        "name": "solaris-dev-shop-opencode", "version": plugin_version, "type": "module",
        "description": identity["description"], "license": "MIT", "repository": DISTRIBUTION,
        "exports": {".": "./native/opencode.mjs"}, "dependencies": {"@opencode/plugin": SDK_VERSION}})
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
    readme = native_readme(version, commit)
    (target / "README.md").write_text(readme, encoding="utf-8")
    (destination / "README.md").write_text(readme.replace("](docs/", "](plugin/docs/").replace("](SOURCE-README.md)", "](plugin/SOURCE-README.md)").replace("](LICENSE)", "](plugin/LICENSE)").replace("](DATA-HANDLING.md)", "](plugin/DATA-HANDLING.md)"), encoding="utf-8")
    write_json(target / "SOLARIS-BUILD-SOURCE.json", {
        "source_commit": commit, "source_repository": REPOSITORY,
        "source_version": version, "native_version": plugin_version,
        "native_formats": ["agent-plugins-1.0", "claude-code", "opencode-v2"],
        "employee_roles": 61, "coordinators": 1, "discovery_adapters": 62,
        "canonical_files": canonical_manifest, "source_path_map": relocation,
        "omitted_repository_config": [".gitignore"],
        "packager_sha256": digest(Path(__file__).read_bytes()), "listing_icon_sha256": digest(icon),
        "official_listing_approved": False,
        "limits": "Native format support is separate from directory approval and model-driven activation. See the recorded host tests for their exact scope."})
    write_json(destination / ".agents/plugins/marketplace.json", {
        "name": MARKETPLACE, "plugins": [{"name": "solaris-dev-shop",
        "source": {"source": "local", "path": "./plugin"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
        "category": "Developer Tools"}]})
    write_json(destination / ".claude-plugin/marketplace.json", {
        "name": MARKETPLACE, "owner": identity["author"], "version": plugin_version,
        "description": "Solaris Technologies native specialist workflows.",
        "plugins": [{"name": "solaris-dev-shop", "source": "./plugin"}]})
    archive_path = destination / ("solaris-dev-shop-" + plugin_version + "-plugin.zip")
    timestamp = datetime.datetime.fromtimestamp(int(git("show", "-s", "--format=%ct", commit)), datetime.timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for file in sorted(target.rglob("*")):
            if file.is_file():
                info = zipfile.ZipInfo(str(file.relative_to(target)), timestamp)
                info.create_system = 3
                info.external_attr = (0o100755 if file.stat().st_mode & 0o111 else 0o100644) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, file.read_bytes(), compresslevel=9)
    write_json(destination / "BUILD.json", {
        "source_commit": commit, "source_version": version, "plugin_version": plugin_version,
        "native_formats": ["Codex/OpenAI", "Claude Code", "OpenCode V2"],
        "canonical_source_files": len(source), "canonical_shipped_files": len(canonical_manifest),
        "employee_roles": 61, "coordinators": 1, "new_capabilities_from_adapters": 0,
        "archive": archive_path.name, "archive_sha256": digest(archive_path.read_bytes()),
        "packager_sha256": digest(Path(__file__).read_bytes()), "published": False})
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
