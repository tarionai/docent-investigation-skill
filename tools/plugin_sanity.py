"""Local reproduction of the upstream `plugin-sanity` checks, parameterized to this repo's plugin.

Run from anywhere: `python tools/plugin_sanity.py`. Exits non-zero on any violation (fails closed).
`check(repo_root)` returns a list of error strings (empty == OK) so tests can drive it without a subprocess.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PLUGIN_NAME = "docent-investigation"
# Dirs that are not part of the plugin's own source — never scanned for forbidden files.
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "data",
             "node_modules", ".mypy_cache", ".ruff_cache", "build", "dist"}
PLUGIN_DIR = Path("plugins") / PLUGIN_NAME
SKILL_DIR = PLUGIN_DIR / "skills" / "investigation"

# Single source of truth for the declared skill-file set. Node N3 extends this in one place.
SKILL_FILES = ("SKILL.md", "rubric-reference.md", "oracle-anchor.md")

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
FORBIDDEN_EXACT = (".mcp.local.json", "docent.env")


def _load_json(root: Path, rel: Path, errors: list[str]) -> object | None:
    path = root / rel
    if not path.is_file():
        errors.append(f"missing JSON file: {rel.as_posix()}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"invalid JSON in {rel.as_posix()}: {exc}")
        return None


def _check_plugin_json(plugin: object, errors: list[str]) -> str | None:
    if not isinstance(plugin, dict):
        errors.append("plugin.json is not a JSON object")
        return None
    if plugin.get("name") != PLUGIN_NAME:
        errors.append(f"plugin.json name != {PLUGIN_NAME!r} (got {plugin.get('name')!r})")
    version = plugin.get("version")
    if not (isinstance(version, str) and SEMVER.match(version)):
        errors.append(f"plugin.json version is not semver: {version!r}")
        return None
    return version


def _check_marketplace_json(market: object, plugin_version: str | None, errors: list[str]) -> None:
    if not isinstance(market, dict):
        errors.append("marketplace.json is not a JSON object")
        return
    entries = [p for p in market.get("plugins", []) if isinstance(p, dict) and p.get("name") == PLUGIN_NAME]
    if not entries:
        errors.append(f"marketplace.json has no plugin entry named {PLUGIN_NAME!r}")
        return
    entry = entries[0]
    expected_source = f"./{PLUGIN_DIR.as_posix()}"
    if entry.get("source") != expected_source:
        errors.append(f"marketplace.json source != {expected_source!r} (got {entry.get('source')!r})")
    if plugin_version is not None and entry.get("version") != plugin_version:
        errors.append(
            f"marketplace.json version {entry.get('version')!r} != plugin.json version {plugin_version!r}"
        )


def _check_mcp_json(mcp: object, errors: list[str]) -> None:
    if not isinstance(mcp, dict):
        errors.append(".mcp.json is not a JSON object")
        return
    docent = mcp.get("mcpServers", {}).get("docent") if isinstance(mcp.get("mcpServers"), dict) else None
    if not isinstance(docent, dict):
        errors.append(".mcp.json mcpServers.docent missing or not an object")
        return
    if docent.get("type") != "stdio":
        errors.append(f".mcp.json docent.type != 'stdio' (got {docent.get('type')!r})")
    if docent.get("command") != "uv":
        errors.append(f".mcp.json docent.command != 'uv' (got {docent.get('command')!r})")
    args = docent.get("args")
    if not (isinstance(args, list) and "--from" in args):
        errors.append(".mcp.json docent.args is not a list containing '--from'")


def _check_skill_files(root: Path, errors: list[str]) -> None:
    for name in SKILL_FILES:
        rel = SKILL_DIR / name
        path = root / rel
        if not path.is_file():
            errors.append(f"missing skill file: {rel.as_posix()}")
        elif not path.read_text(encoding="utf-8").strip():
            errors.append(f"empty skill file: {rel.as_posix()}")


def _check_forbidden(root: Path, errors: list[str]) -> None:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name in FORBIDDEN_EXACT or name.startswith("docent.env"):
                rel = Path(dirpath, name).relative_to(root).as_posix()
                errors.append(f"forbidden file present: {rel}")


def check(repo_root: Path | str) -> list[str]:
    root = Path(repo_root)
    errors: list[str] = []
    market = _load_json(root, Path(".claude-plugin") / "marketplace.json", errors)
    plugin = _load_json(root, PLUGIN_DIR / ".claude-plugin" / "plugin.json", errors)
    mcp = _load_json(root, PLUGIN_DIR / ".mcp.json", errors)

    plugin_version = _check_plugin_json(plugin, errors) if plugin is not None else None
    if market is not None:
        _check_marketplace_json(market, plugin_version, errors)
    if mcp is not None:
        _check_mcp_json(mcp, errors)
    _check_skill_files(root, errors)
    _check_forbidden(root, errors)
    return errors


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    errors = check(root)
    if errors:
        print("PLUGIN SANITY: FAIL")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("PLUGIN SANITY: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
