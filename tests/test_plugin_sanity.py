import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import plugin_sanity  # noqa: E402


def test_real_tree_passes():
    assert plugin_sanity.check(ROOT) == []


def _clone(tmp_path: Path) -> Path:
    dst = tmp_path / "repo"
    shutil.copytree(
        ROOT, dst,
        ignore=shutil.ignore_patterns(".git", ".venv", "venv", "__pycache__", ".pytest_cache", "data"),
    )
    return dst


def test_broken_version_match_fails_closed(tmp_path):
    dst = _clone(tmp_path)
    plugin_json = dst / "plugins" / "docent-investigation" / ".claude-plugin" / "plugin.json"
    data = json.loads(plugin_json.read_text(encoding="utf-8"))
    data["version"] = "9.9.9"
    plugin_json.write_text(json.dumps(data), encoding="utf-8")
    errors = plugin_sanity.check(dst)
    assert any("version" in e for e in errors), errors


def test_empty_skill_file_fails_closed(tmp_path):
    dst = _clone(tmp_path)
    (dst / "plugins" / "docent-investigation" / "skills" / "investigation" / "SKILL.md").write_text(
        "", encoding="utf-8"
    )
    errors = plugin_sanity.check(dst)
    assert any("empty skill file" in e for e in errors), errors


def test_forbidden_file_fails_closed(tmp_path):
    dst = _clone(tmp_path)
    (dst / "docent.env").write_text("SECRET=x", encoding="utf-8")
    errors = plugin_sanity.check(dst)
    assert any("forbidden file" in e for e in errors), errors


def test_bad_mcp_command_fails_closed(tmp_path):
    dst = _clone(tmp_path)
    mcp_json = dst / "plugins" / "docent-investigation" / ".mcp.json"
    data = json.loads(mcp_json.read_text(encoding="utf-8"))
    data["mcpServers"]["docent"]["command"] = "npx"
    mcp_json.write_text(json.dumps(data), encoding="utf-8")
    errors = plugin_sanity.check(dst)
    assert any("command" in e for e in errors), errors
