---
name: investigation
description: Drive a complete, honest behavioral investigation on Docent — ingest agent runs, author and evaluate a rubric for a failure mode, measure flag-frequency, anchor against a ground-truth oracle, and report honestly.
alwaysApply: false
---

# Investigation (placeholder — authored in node N3)

This skill walks Claude through an end-to-end behavioral investigation on Docent:

1. Ingest real agent runs into a Docent collection.
2. Author a rubric for one target failure mode (v1: **false-success declaration**).
3. Evaluate the rubric via the Docent SDK and read run-state.
4. Compute flag-frequency over the sample.
5. Anchor flags against a ground-truth oracle (resolved/unresolved) and report honestly, including nulls.

> This file is a non-empty scaffold placeholder. The full procedure prose, with validated Docent SDK
> method names, is written in node **N3** of `docs/plans/IMPLEMENTATION_PLAN.md`. See
> `rubric-reference.md` and `oracle-anchor.md` in this directory for the supporting references.
