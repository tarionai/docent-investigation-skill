# Rubric reference (placeholder — authored in node N3)

Reference for authoring and evaluating a Docent rubric via the SDK (validated 2026-06-27):

- Create: `client.create_rubric(collection_id, rubric)` → `rubric_id`, where `rubric` is
  `docent.judges.types.Rubric(rubric_text=..., output_schema=...)`.
- Evaluate: `client.start_rubric_eval_job(collection_id, rubric_id, max_agent_runs=...)` → `job_id`.
- Read results: `client.get_rubric_run_state(collection_id, rubric_id, ...)` (does not start the job; poll after).

> Non-empty scaffold placeholder. Full rubric text and `output_schema` for the false-success-declaration
> target behavior are written in node N3.
