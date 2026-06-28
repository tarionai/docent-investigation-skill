---
name: investigation
description: Drive a complete, honest behavioral investigation on Docent — ingest agent runs, author and evaluate a rubric for a failure mode, measure flag-frequency, anchor against an independent resolution oracle (a third-party proxy, not ground truth), and report honestly (including nulls). Use when asked to investigate, measure, or audit a behavior across a set of AI agent runs with Docent.
alwaysApply: false
---

# Investigation: an honest behavioral investigation on Docent

This skill walks you (Claude) through one complete, **non-circular** behavioral investigation on
[Docent](https://docs.transluce.org): ingest real agent runs → author a rubric for one failure mode →
evaluate it → measure flag-frequency → **anchor the rubric against an independent resolution oracle** → report
honestly, including nulls. The anchoring step is what separates this from a self-graded demo.

The `docent` MCP server (declared in this plugin's `.mcp.json`) exposes Docent at runtime. For batch
work, the Python package `docent` (>= 0.1.74) is the engine; this repo's `docent_investigation` package
wraps it. Authenticate by setting `DOCENT_API_KEY` (and `DOCENT_DOMAIN`) in the environment — never commit
them; `.mcp.local.json` / `docent.env*` are forbidden by `tools/plugin_sanity.py`.

## The one rule that makes it honest

**The rubric judge must be blind to the oracle.** Store the resolution label (e.g. resolved/unresolved) only in
`AgentRun.metadata`, and always evaluate with `include_metadata=False`. Pre-register the rubric and the
decision thresholds *before* looking at results (see `oracle-anchor.md`). If you skip this, you have a
circular demo, not a measurement.

## Procedure

### 1. Pick the behavior and an oracle (first principles) — the admissibility test
The non-circularity guarantee holds **only** for behaviors that pass both conditions. State them before
you start — this admissibility boundary is the load-bearing contribution of the skill, not a footnote:
1. **Transcript-detectable** — the behavior is judgeable from the transcript *alone*, no outside knowledge.
2. **Externally checkable** — an oracle exists that is *external to and withheld from* the transcript and
   the judge, so the judge cannot see it yet it independently scores the outcome.

The reference target — **false-success declaration** (the agent declares the task done while it actually
failed) — passes both: the claim is in the transcript; SWE-bench resolution is computed outside it and
hidden from the judge.

**Worked negative (the boundary is real).** "Tool-call hallucination" (did the agent invent a tool
result?) *fails* condition 2 — the only oracle is the execution log, which lives *inside* the transcript,
so the judge cannot be blind to it. That behavior is not oracle-anchorable here; forcing it through this
skill would be circular. Don't.

If no external oracle exists you can still run a **fidelity study** — blind human labels (N≈30) scoring
the behavior directly — but that is a *different* epistemic claim (human-vs-judge agreement), **not** the
outcome anchoring this skill teaches. Report it as such; prefer a real external oracle. See `oracle-anchor.md`.

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
from docent_investigation.anchor import Row, compute_anchor, evaluate_decision
rows = join_rows(adapter, cid, verdicts)              # recovers instance_id + oracle from metadata
stats = compute_anchor([Row(r["instance_id"], r["resolved"], r["rubric_label"]) for r in rows])
decision = evaluate_decision(stats)                   # verdict on the primary estimand (its CI)
```
`compute_anchor` returns pure measurement — the 2×2 cross-tab, the false-success rate **with a Wilson
95% interval**, and a Fisher exact p-value. `evaluate_decision` applies your pre-registered rule on the
primary estimand and returns the verdict (`oracle-anchor.md`).

### 6. Check label fidelity (audit the instrument, not just the outcome)
The oracle validates outcomes; it says nothing about whether the rubric *labeled* correctly. Run the
label-fidelity check and report it honestly:
```python
from docent_investigation.fidelity import label_fidelity
fid = label_fidelity(rows)            # rows from join_rows carry the judge's cited explanation
```
`judge_self_consistency` (do `declared_success` citations contain completion language?) is a **weak
self-consistency sanity check — never report it as fidelity.** The real measure is human agreement:
blind-label a sample by hand and pass `human_labels=` to get raw agreement + Cohen's κ (one rater is a
weak bound; two + adjudication is the standard). Always surface `fid.disclosure`.

### 7. Report honestly
State the flag-frequency, the 2×2, and the metrics. Report **two results separately**: the
pre-registered **verdict** on the primary estimand (`evaluate_decision` → `SUPPORTED` /
`NOT_SUPPORTED` / `UNDEFINED`, keyed on its CI), and the **association** (Fisher p) as a descriptive
aside — never conjoin them. Name the blind spot: the oracle validates the *outcome*, not the rubric's
label fidelity (report the `label_fidelity` signals from step 6). Do not round a `NOT_SUPPORTED`
estimand up to a finding just because the association is significant.

The whole pipeline is driven end-to-end by `scripts/run_investigation.py` (with a `--collection-id`
resume path), and the worked reference investigation is summarized in `reports/INVESTIGATION_REPORT.md`.
