# docent-investigation-skill

A Claude Code plugin marketplace whose `docent-investigation` plugin ships an **`investigation`** skill:
it drives a complete, honest behavioral investigation on [Docent](https://docs.transluce.org) — ingest
real agent runs → author + evaluate a rubric for a failure mode via the Docent SDK → measure
flag-frequency → anchor against a ground-truth oracle → report honestly (including nulls).

Layout mirrors the `TransluceAI/claude-code-plugins` marketplace pattern.

## Install

```
/plugin marketplace add tarionai/docent-investigation-skill
```

## Repo layout

```
.claude-plugin/marketplace.json          # marketplace manifest
plugins/docent-investigation/
  .claude-plugin/plugin.json             # plugin manifest
  .mcp.json                              # docent MCP server (uv tool run --from docent-python>=0.1.74 docent-mcp)
  skills/investigation/                  # the skill (SKILL.md + references)
tools/plugin_sanity.py                   # local structural validation (run before commit)
docs/plans/                              # implementation plan + bounded node prompts
```

## Validate the scaffold

```
python tools/plugin_sanity.py
python -m pytest -q
```

## Status

Built under the `/vneg-build` plan-gated pipeline. See `docs/plans/IMPLEMENTATION_PLAN.md`. Node **N0**
(this scaffold) is complete; the live investigation nodes are gated on external Docent access
(see the plan's §9 BLOCKER).
