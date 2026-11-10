#!/usr/bin/env python3
"""Validate the per-platform plugin manifests stay consistent.

A multi-manifest repo drifts silently: one manifest bumps, another keeps the old
version, a skills path points nowhere. These are cheap structural checks, all
offline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PLUGIN_MANIFESTS = [
    "plugin.json",
    ".claude-plugin/plugin.json",
    ".codex-plugin/plugin.json",
]
MARKETPLACES = [
    "marketplace.json",
    ".claude-plugin/marketplace.json",
    ".omp-plugin/marketplace.json",
    ".agents/plugins/marketplace.json",
]


def load(rel: str):
    p = ROOT / rel
    if not p.is_file():
        return None, f"missing {rel}"
    try:
        return json.loads(p.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as e:
        return None, f"{rel} is not valid JSON: {e}"


def main() -> int:
    fails = 0

    def check(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        print(f"{'PASS' if ok else 'FAIL'}  {name}{'' if ok else ': ' + detail}")
        if not ok:
            fails += 1

    manifests = {}
    for rel in PLUGIN_MANIFESTS:
        data, err = load(rel)
        manifests[rel] = data
        check(f"{rel} parses", err is None, err or "")

    # Every manifest must agree on identity and version.
    names = {rel: (d or {}).get("name") for rel, d in manifests.items() if d}
    check("all plugin manifests share one name",
          len(set(names.values())) == 1, str(names))
    versions = {rel: (d or {}).get("version") for rel, d in manifests.items() if d}
    check("all plugin manifests share one version",
          len(set(versions.values())) == 1, str(versions))

    # The root manifest must satisfy Agent Plugins 1.0.0: $schema + name are
    # required, and the schema is closed (additionalProperties: false), so a
    # "skills" key here is invalid -- skills are discovered from skills/.
    root = manifests.get("plugin.json") or {}
    check("root plugin.json declares $schema", "$schema" in root)
    if "$schema" in root:
        check("root plugin.json $schema is the 1.0.0 identifier",
              root["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
              str(root.get("$schema")))
    allowed = {"$schema", "name", "version", "description", "author", "homepage",
               "repository", "license", "keywords", "extensions"}
    extra = set(root) - allowed
    check("root plugin.json has no keys the closed schema forbids", not extra, str(extra))

    root_pkg, err = load("package.json")
    check("package.json parses", err is None, err or "")
    if root_pkg and versions:
        check("package.json version matches plugin manifests",
              root_pkg.get("version") in set(versions.values()),
              f"package.json {root_pkg.get('version')} vs {set(versions.values())}")

    # Declared content paths must exist, or a plugin install loads nothing.
    for rel, data in manifests.items():
        if not data:
            continue
        skills = data.get("skills")
        for path in ([skills] if isinstance(skills, str) else (skills or [])):
            check(f"{rel} skills path exists ({path})", (ROOT / path).is_dir())
        cmds = data.get("commands")
        if cmds:
            for path in ([cmds] if isinstance(cmds, str) else cmds):
                check(f"{rel} commands path exists ({path})", (ROOT / path).exists())

    for rel in MARKETPLACES:
        data, err = load(rel)
        check(f"{rel} parses", err is None, err or "")
        if not data:
            continue
        entries = data.get("plugins") or []
        check(f"{rel} lists a plugin", bool(entries))
        for entry in entries:
            check(f"{rel} entry has name+source",
                  bool(entry.get("name")) and "source" in entry, str(entry))
            if "version" in entry and versions:
                check(f"{rel} entry version matches manifests",
                      entry["version"] in set(versions.values()),
                      f"{entry['version']} vs {set(versions.values())}")

    # The command template must carry a placeholder installer can substitute and
    # a resolver fallback so the same file works when a plugin manager installs it.
    cmd = ROOT / "commands" / "seo-audit.md"
    if cmd.is_file():
        text = cmd.read_text(encoding="utf-8")
        check("command keeps the @SKILL_DIR@ placeholder", "@SKILL_DIR@" in text)
        check("command has a runtime fallback for plugin installs",
              "PLUGIN_ROOT" in text or "CLAUDE_PLUGIN_ROOT" in text)
        check("command has frontmatter description",
              text.startswith("---") and "description:" in text.split("---")[1])

    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
