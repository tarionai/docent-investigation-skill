# Oracle anchor reference (placeholder — authored in node N3/N5)

How the investigation stays honest: cross-tab rubric flags against a ground-truth oracle.

- Oracle source: SWE-bench Verified `logs/<instance_id>/report.json` → resolved/unresolved.
- Cross-tab: rubric flag (false-success) × oracle (unresolved) → precision/recall.
- Pre-register thresholds before looking at results; report nulls if the rubric does not separate.

> Non-empty scaffold placeholder. The pre-registration and the precision/recall computation live in
> node N5 (`PRE_REGISTRATION.md`, `src/docent_investigation/anchor.py`).
