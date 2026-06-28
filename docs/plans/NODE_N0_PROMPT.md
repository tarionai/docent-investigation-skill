# Bounded implementation prompt — Node N0 (scaffold + local sanity harness)

> This is the ONLY context the N0 implementer receives. Do not pull in the full architecture, future
> nodes, or chat history. Build exactly N0.

## Node contract
Stand up an installable Claude Code plugin-marketplace skeleton for a standalone repo and a local Python
sanity check that reproduces the upstream `plugin-sanity` validation logic, parameterized to THIS repo's
plugin. No application logic. Skill markdown files are non-empty placeholders only (real prose is N3).

Repo root: `C:\PLATFORMS\PROJECTS\docent-investigation-skill` (already `git init`, branch `main`).

## Machine-readable contract (build to these exact shapes)
**`.claude-plugin/marketplace.json`:**
```json
{
  "name": "tarionai-plugins",
  "owner": "tarionai",
  "metadata": { "description": "Docent behavioral-investigation tooling for Claude Code" },
  "plugins": [
    {
      "name": "docent-investigation",
      "source": "./plugins/docent-investigation",
      "description": "A Claude Code skill that drives an honest behavioral investigation on Docent.",
      "version": "0.1.0",
      "author": "tarionai",
      "tags": ["analysis", "ai", "mcp", "evaluation", "docent"]
    }
  ]
}
```
**`plugins/docent-investigation/.claude-plugin/plugin.json`:**
```json
{ "name": "docent-investigation", "version": "0.1.0", "description": "A Claude Code skill that drives an honest behavioral investigation on Docent." }
```
**`plugins/docent-investigation/.mcp.json`** (mirror upstream verbatim):
```json
{ "mcpServers": { "docent": { "type": "stdio", "command": "uv", "args": ["tool", "run", "--from", "docent-python>=0.1.74", "docent-mcp"] } } }
```
**`plugins/docent-investigation/skills/investigation/SKILL.md`** frontmatter (body = non-empty placeholder):
```yaml
---
name: investigation
description: Drive a complete, honest behavioral investigation on Docent — ingest agent runs, author and evaluate a rubric for a failure mode, measure flag-frequency, anchor against a ground-truth oracle, and report honestly.
alwaysApply: false
---
```
**Declared skill-file set for THIS plugin** (each must exist + be non-empty; placeholders OK for N0):
`SKILL.md`, `rubric-reference.md`, `oracle-anchor.md`. (NOT Transluce's fixed 7-file `docent` set.)

## Relevant primitives
None — N0 is static files + a validator. No `src/` types yet.

## Direct dependency interfaces
None (leaf node).

## What `tools/plugin_sanity.py` must assert (parameterized; exit non-zero on any failure)
1. `.claude-plugin/marketplace.json`, `plugins/docent-investigation/.claude-plugin/plugin.json`,
   `plugins/docent-investigation/.mcp.json` all parse as JSON.
2. `plugin.json.name == "docent-investigation"`; `version` matches `^\d+\.\d+\.\d+$`.
3. The `marketplace.json` plugin entry for `docent-investigation` has `version` == `plugin.json.version`
   and `source == "./plugins/docent-investigation"`.
4. `.mcp.json.mcpServers.docent` is an object with `type=="stdio"`, `command=="uv"`, and `args` is a list
   containing `"--from"`.
5. Every file in the declared skill-file set exists under `plugins/docent-investigation/skills/investigation/`
   and is non-empty (read the set from a small `SKILL_FILES` constant in the script).
6. No file named `.mcp.local.json`, `docent.env`, or matching `docent.env.*` exists anywhere in the repo.
Read the declared file set from one constant so N3 can extend it in one place (single source of truth).

## Allowed files
`.claude-plugin/marketplace.json`, `plugins/docent-investigation/**`, `tools/plugin_sanity.py`,
`tests/test_plugin_sanity.py`, `README.md`, `.gitignore`, `pyproject.toml`.

## Forbidden files
`src/**` (no logic), any `.mcp.local.json`, any `docent.env*`, anything under the upstream Transluce repo,
any skill prose beyond non-empty placeholders.

## Required tests
- `tools/plugin_sanity.py` itself is the primary check (exit 0 on the valid tree).
- `tests/test_plugin_sanity.py`: (a) passes on the real tree; (b) a fixture with a broken manifest
  (bad version match) makes the check exit non-zero — proves it fails closed.

## Completion commands
```
python tools/plugin_sanity.py
python -m pytest tests/test_plugin_sanity.py -q
```
Both must succeed.

## Completion-report format (write to `docs/verification/N0.md`)
- Node: N0
- Commands run + exit codes (verbatim).
- Files created (paths).
- Invariants confirmed (checklist 1–6 above).
- Anything deferred + why.
- Next executable node: N1 (per the plan) — and whether it is unblocked.
