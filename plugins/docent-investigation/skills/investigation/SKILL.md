---
name: investigation
description: Drive a complete, honest behavioral investigation on Docent — ingest agent runs, author and evaluate a rubric for a failure mode, measure flag-frequency, anchor against a ground-truth oracle, and report honestly (including nulls). Use when asked to investigate, measure, or audit a behavior across a set of AI agent runs with Docent.
alwaysApply: false
---

# Investigation: an honest behavioral investigation on Docent

This skill walks you (Claude) through one complete, **non-circular** behavioral investigation on
[Docent](https://docs.transluce.org): ingest real agent runs → author a rubric for one failure mode →
evaluate it → measure flag-frequency → **anchor the rubric against a ground-truth oracle** → report
honestly, including nulls. The anchoring step is what separates this from a self-graded demo.

The `docent` MCP server (declared in this plugin's `.mcp.json`) exposes Docent at runtime. For batch
work, the Python package `docent` (>= 0.1.74) is the engine; this repo's `docent_investigation` package
wraps it. Authenticate by setting `DOCENT_API_KEY` (and `DOCENT_DOMAIN`) in the environment — never commit
them; `.mcp.local.json` / `docent.env*` are forbidden by `tools/plugin_sanity.py`.

## The one rule that makes it honest

**The rubric judge must be blind to the oracle.** Store ground truth (e.g. resolved/unresolved) only in
`AgentRun.metadata`, and always evaluate with `include_metadata=False`. Pre-register the rubric and the
decision thresholds *before* looking at results (see `oracle-anchor.md`). If you skip this, you have a
circular demo, not a measurement.

## Procedure

### 1. Pick the behavior and an oracle (first principles)
Choose a failure mode that is **operationally meaningful and oracle-checkable**. The reference target is
**false-success declaration** (the agent declares the task done while it actually failed) because it is
directly checkable against SWE-bench's resolved/unresolved label. If no clean oracle exists, fall back to
a blind human-labeled sample (N≈30) — but prefer a real oracle. See `oracle-anchor.md`.

### 2. Ingest real runs into a collection
Convert agent traces to `AgentRun(transcripts=[Transcript(messages=[...])], metadata=...)`, preserving
per-step tool calls. Then:
```python
from docent_investigation.docent_client import DocentClientAdapter
adapter = DocentClientAdapter()                       # reads DOCENT_API_KEY from env
cid = adapter.create_collection("my investigation", "N real agent runs")
adapter.ingest(cid, runs)                             # client.add_agent_runs
url = adapter.make_public(cid)                        # citable: others can open + re-run
```
A working transform for OpenHands SWE-bench traces lives in `docent_investigation.transform`; reuse it as
a template for other scaffolds. `scripts/fetch_traces.py` pulls a public trace set + its oracle.

### 3. Author the rubric (blind to the oracle)
See `rubric-reference.md` for the exact SDK calls and the frozen reference rubric. In short:
```python
from docent_investigation.rubric import false_success_rubric
rubric_id = adapter.create_rubric(cid, false_success_rubric())
```

### 4. Evaluate — judge stays blind
```python
adapter.evaluate(cid, rubric_id, max_agent_runs=N)    # forces include_metadata=False
verdicts = adapter.wait_for_verdicts(cid, rubric_id, expected=N)
```

### 5. Measure flag-frequency and anchor against the oracle
```python
from docent_investigation.batch import join_rows
from docent_investigation.anchor import Row, compute_anchor
rows = join_rows(adapter, cid, verdicts)              # recovers instance_id + oracle from metadata
stats = compute_anchor([Row(r["instance_id"], r["resolved"], r["rubric_label"]) for r in rows])
```
`compute_anchor` returns the 2×2 cross-tab, the false-success rate, a Fisher exact p-value, and a
decision computed from your pre-registered rules (`oracle-anchor.md`).

### 6. Report honestly
State the flag-frequency, the 2×2, the metrics, and the **decision your pre-registration dictates** —
including NULL / INCONCLUSIVE. Name the blind spot: the oracle validates the *outcome*, not the rubric's
label fidelity (that needs human labels). Do not round an inconclusive result up to a finding.

The whole pipeline is driven end-to-end by `scripts/run_investigation.py` (with a `--collection-id`
resume path), and the worked reference investigation is summarized in `reports/INVESTIGATION_REPORT.md`.
