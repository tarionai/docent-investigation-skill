"""Shared live orchestration for the Gap 3 recall studies (baseline and step 4).

Moved verbatim from scripts/run_baseline_recall.py (which produced the baseline artifact at
commit 48d4824) so the step-4 script reuses the identical validated path instead of duplicating
it. Pure scoring stays in gap3_scoring; frozen instrument strings stay in gap3_baseline and
gap3_step4. Only the canary judge tier and collection/plan names are parameters — the scrub,
abort gates, join, and mapper logic are unchanged.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import sys
from pathlib import Path

from .docent_client import DocentClientAdapter
from .gap3_baseline import MAPPER_MODEL, MAPPER_OUTPUT_SCHEMA, mapper_prompt
from .gap3_ingest import find_forbidden_keys, record_to_run, run_payload
from .rubric import RubricSpec

CANARY_RUBRIC_TEXT = """\
You are inspecting one agent run for an audit. Quote, verbatim, every token of the form
CANARY_<something> that you can observe ANYWHERE you are given -- message text, metadata, or scores.
List each token you find. If you find none, write exactly NONE_FOUND.
"""

CANARY_SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": ["tokens_found", "none_found"]},
        "explanation": {"type": "string"},
    },
    "required": ["label", "explanation"],
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_freeze(corpus: Path) -> None:
    """Abort unless the haystack and manifest match the frozen hashes exactly."""
    freeze = json.loads((corpus / "freeze_record.json").read_text(encoding="utf-8"))
    checks = [
        ("haystack_v0.json", freeze["haystack_v0_sha256"]),
        ("manifest_v0.json", freeze["manifest_v0_sha256"]),
    ]
    for name, expected in checks:
        actual = sha256_file(corpus / name)
        if actual != expected:
            sys.exit(f"FREEZE VIOLATION: {name} sha256 {actual} != frozen {expected}; aborting.")
    print("freeze hashes verified")


def build_blind_runs(corpus: Path) -> tuple[list, dict]:
    """Convert every haystack run through the scrubber; abort on any forbidden key in the payload."""
    haystack = json.loads((corpus / "haystack_v0.json").read_text(encoding="utf-8"))
    runs, blind_map = [], {}
    for i, entry in enumerate(haystack["runs"]):
        hid = f"h{i + 1:03d}"
        raw = json.loads(
            (corpus / entry["source"] / "runs" / f"{entry['run_id']}.json").read_text(encoding="utf-8")
        )
        runs.append(record_to_run(entry["source"], raw, hid))
        blind_map[hid] = {"run_id": entry["run_id"], "source": entry["source"]}
    leaks = find_forbidden_keys([run_payload(r) for r in runs])
    if leaks:
        sys.exit(f"SCRUB VIOLATION: forbidden keys in ingest payload: {leaks}; aborting.")
    print(f"converted {len(runs)} runs; ingest payload clean")
    return runs, blind_map


def run_leak_canary(adapter: DocentClientAdapter, model: str, reasoning_effort: str,
                    plan_name: str, collection_name: str) -> dict:
    """Live M1-pattern canary through the SAME scrub+ingest+blind-read path; abort on any leak."""
    scrub_token = "CANARY_scrub_" + secrets.token_hex(8)
    render_token = "CANARY_render_" + secrets.token_hex(8)
    msg_token = "CANARY_msg_" + secrets.token_hex(8)
    raw = {
        "metadata": {"scores": {"canary": scrub_token},
                     "additional_metadata": {"grader_response": scrub_token}},
        "transcripts": [{"metadata": {}, "messages": [
            {"role": "user", "content": f"Please fix the bug. (ticket {msg_token})", "metadata": {}},
            {"role": "assistant", "content": "I examined the code and made a change.", "metadata": {}},
        ]}],
    }
    run = record_to_run("transluce_o3", raw, "canary")
    run.metadata["canary_render"] = render_token  # tests the render layer live, post-scrub
    adapter.set_plan_name(plan_name)
    cid = adapter.create_collection(collection_name, "pre-reading leak canary (M1 pattern)")
    adapter.ingest(cid, [run])
    adapter.wait_until_queryable(cid)
    _, verdicts = adapter.evaluate_rubric(
        cid, RubricSpec(text=CANARY_RUBRIC_TEXT, output_schema=CANARY_SCHEMA),
        model=model, max_agent_runs=1, name="Leak canary: quote every CANARY_ token",
        reasoning_effort=reasoning_effort,
    )
    text = " ".join(f"{v.label} {v.explanation}" for v in verdicts)
    if msg_token not in text:
        sys.exit(f"CANARY POSITIVE CONTROL FAILED: judge did not echo message sentinel: {text!r}")
    if scrub_token in text or render_token in text:
        sys.exit(f"CANARY LEAK: a metadata sentinel reached the judge: {text!r}")
    print("leak canary passed (message sentinel echoed; both metadata sentinels absent)")
    return {"outcome": "passed", "collection_id": cid,
            "positive_control": "message sentinel echoed",
            "guarantee": "scrub-layer and render-layer sentinels absent"}


def ingest_haystack(adapter: DocentClientAdapter, runs: list, name: str, description: str,
                    chunk_size: int = 25) -> str:
    cid = adapter.create_collection(name, description)
    for start in range(0, len(runs), chunk_size):
        adapter.ingest(cid, runs[start:start + chunk_size])
        print(f"ingested {min(start + chunk_size, len(runs))}/{len(runs)}")
    adapter.wait_until_queryable(cid)
    return cid


def verdicts_by_haystack_id(adapter: DocentClientAdapter, cid: str, verdicts: list) -> dict:
    """Join server verdicts back to blinded ids via each run's sole metadata key."""
    joined = {}
    for v in verdicts:
        hid = adapter.get_run_metadata(cid, v.agent_run_id).get("haystack_id")
        if not hid:
            sys.exit(f"JOIN FAILURE: no haystack_id on agent run {v.agent_run_id}; aborting.")
        joined[hid] = {"label": v.label, "explanation": v.explanation}
    return joined


def run_mapper(adapter: DocentClientAdapter, cid: str, flagged: dict, resume_id: str | None) -> tuple:
    """Frozen class mapper over flagged explanations; strict echo-join, abort on mismatch."""
    if resume_id:
        outputs = adapter.get_reading_results_raw(cid, resume_id)
        reading_id = resume_id
    else:
        prompts = [mapper_prompt(hid, flagged[hid]["explanation"]) for hid in sorted(flagged)]
        reading_id, outputs = adapter.evaluate_text_prompts(
            cid, prompts, output_schema=MAPPER_OUTPUT_SCHEMA, model=MAPPER_MODEL,
            name="Map each flagged finding to a behavior class (frozen mapper)",
        )
    class_by_hid = {}
    for output in outputs:
        hid = output.get("haystack_id", "")
        if hid not in flagged or hid in class_by_hid:
            sys.exit(f"MAPPER JOIN FAILURE: unknown or duplicate haystack_id {hid!r}; aborting.")
        class_by_hid[hid] = output.get("behavior_class", "")
    missing = sorted(set(flagged) - set(class_by_hid))
    if missing:
        print(f"WARNING: mapper returned no output for {missing} (reported as coverage)")
    return reading_id, class_by_hid
