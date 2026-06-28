# docent-investigation-skill

A Claude Code plugin marketplace whose `docent-investigation` plugin ships an **`investigation`** skill:
it drives a complete, honest behavioral investigation on [Docent](https://docs.transluce.org) — ingest
real agent runs → author + evaluate a rubric for a failure mode via the Docent SDK → measure
flag-frequency → anchor against an independent resolution oracle (a third-party proxy, not ground
truth) → report honestly (including nulls).

Layout mirrors the `TransluceAI/claude-code-plugins` marketplace pattern.

## Install

Two steps — **adding a marketplace does not install the plugin**:

```
/plugin marketplace add tarionai/docent-investigation-skill   # 1. register the marketplace
/plugin install docent-investigation@tarionai-plugins         # 2. install the plugin
```

Then invoke the `investigation` skill.

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

Built under the `/vneg-build` plan-gated pipeline (see `docs/plans/IMPLEMENTATION_PLAN.md`). The live
**N=100** investigation has run end to end: see `reports/INVESTIGATION_REPORT.md` for the result and
`reports/labeled_rows.json` for the committed per-run rows.
