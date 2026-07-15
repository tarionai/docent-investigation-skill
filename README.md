# docent-investigation-skill

A Claude Code plugin marketplace whose `docent-investigation` plugin ships an **`investigation`**
skill: an end-to-end behavioral investigation pipeline for [Docent](https://docs.transluce.org). It
ingests real agent runs, authors a rubric for a target failure mode, evaluates it as a blind Docent
reading (the Analysis Plans surface Docent now recommends), measures flag-frequency, and validates
the measurement from both sides: the rubric's labels are anchored against a resolution oracle
withheld from the judge (outcome half), and **the judge itself is measured against blind human
ground-truth labels — precision/recall with Wilson intervals** (instrument half,
`PRE_REGISTRATION_JUDGE_VALIDATION.md`). Verdicts key on pre-registered decision rules (the
reference run returned NOT_SUPPORTED, reported as-is) and recompute offline from committed per-run
rows.

**Worked reference run:** [False-success declaration in SWE-bench Verified agent runs](reports/INVESTIGATION_REPORT.md)
— the skill applied end to end at N=100 (Nemotron-Nano, OpenHands scaffold).

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
**N=100** investigation (Nemotron-Nano on SWE-bench Verified) has run end to end — see the
[investigation report](reports/INVESTIGATION_REPORT.md) for the full result and `reports/labeled_rows.json`
for the committed per-run rows.

**The skill is the product; the N=100 run is illustrative of the method, not a population claim.**

The result is reported as a **split verdict** — the two estimands are never conjoined:

- **Primary estimand — false-success rate** = P(not_resolved | declared_success) = **0.53 (10/19)**,
  Wilson 95% CI **[0.32, 0.73]**, pre-registered threshold 0.50 → **NOT_SUPPORTED**. This means the
  ≥0.50 claim *failed its support criterion* once sampling uncertainty is respected — **not** that the
  rate is below 0.50 (0.53 is the point estimate; the interval straddles the line). Scope: 19
  declared-success runs across 2 repos (astropy, django) — illustrative, not a population rate.
- **Association** (are declarations informative about resolution?): descriptive only, deliberately
  **not** part of the verdict (p=0.002, n=66).

**Judge validation (in progress):** the judge's 19 `declared_success` flags are being validated
against blind human labels of all 100 runs — collected with `scripts/label_runs.py` (the rater sees
the judge's exact blind view; parity enforced by `tests/test_rater_blindness.py`) and scored offline
by `scripts/run_judge_validation.py` (judge precision/recall, agreement, Cohen's κ, pre-registered
precision verdict). Design frozen in `PRE_REGISTRATION_JUDGE_VALIDATION.md` before any label was
collected.

The resolution oracle is a third-party proxy (not ground truth), and a committed leak canary
(`tests/test_metadata_canary.py`) proves it never reaches the blind judge — the exclusion is
structural: an exclude-all context config on the judge's reading, pinned in its content hash. The 2×2 and verdict recompute
offline from the committed rows (`compute_anchor`/`evaluate_decision` → A,B,C,D = 9,10,5,76 →
`NOT_SUPPORTED`), no live judge needed. `PRE_REGISTRATION.md` is frozen; the single correction is
disclosed as a post-hoc amendment (A1).
