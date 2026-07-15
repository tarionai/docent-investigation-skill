"""Scrub + blindness guarantees for the Gap 3 baseline ingest (PRE_REGISTRATION_BASELINE_RECALL).

Three layers, mirroring the pre-registration: (1) structural -- the allowlist converters emit
runs whose metadata is exactly {"haystack_id"} and whose serialized payload contains no forbidden
key, with a positive control proving the detector can see leaks in the raw archives; (2) the MALT
normalizer's frozen sample-selection rule; (3) blind render -- even the haystack_id metadata that
IS ingested never reaches the judge-visible text under the pinned exclude-all config.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path

import pytest

from docent.data_models.agent_run import AgentRunView
from docent.data_models.context_config import AgentRunContextConfig
from docent.data_models.metadata_util import INCLUDE_ALL_GLOB_FILTER

from docent_investigation.docent_client import blind_run_context
from docent_investigation.gap3_ingest import (
    docent_record_to_run,
    find_forbidden_keys,
    malt_record_to_run,
    record_to_run,
    run_payload,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "data" / "gap3_corpus_v0"


def _o3_style_record() -> dict:
    """A synthetic archived record carrying every label-bearing field the scrubber must drop."""
    return {
        "id": "raw-run-id",
        "name": "violation candidate",
        "metadata": {
            "model": "o3",
            "scores": {"score": 4},
            "attack_type": "fabrication",
            "epoch_id": 7,
            "additional_metadata": {
                "violation_score": 4,
                "violation_type": "fabrication",
                "grader_response": "the agent fabricated results",
                "grader_system_prompt": "grade the run",
                "regraded": True,
            },
            "instance_id": "task-123",
            "resolved": False,
            "model_name": "qwen",
        },
        "transcripts": [
            {
                "id": "t-raw",
                "metadata": {"labels": ["bad"]},
                "messages": [
                    {"id": "m1", "role": "user", "content": "Fix the bug.", "metadata": {"k": 1}},
                    {
                        "id": "m2",
                        "role": "assistant",
                        "content": "Working on it.",
                        "model": "o3",
                        "metadata": {},
                        "tool_calls": [{"id": "c1", "function": "bash", "arguments": {"command": "ls"}}],
                    },
                    {"id": "m3", "role": "tool", "content": "ok", "tool_call_id": "c1",
                     "function": "bash", "error": None, "metadata": {}},
                ],
            }
        ],
    }


def _malt_style_record() -> dict:
    short = {
        "input": [
            {"role": "system", "content": "sys", "name": None, "function_call": None, "metadata": {}},
            {"role": "user", "content": "do the task", "name": None, "function_call": None, "metadata": {}},
        ],
        "output": [[{"role": "assistant", "content": "early", "function_call": None}]],
        "metadata": {"unmatched": False},
    }
    long = {
        "input": short["input"]
        + [
            {"role": "assistant", "content": "thinking", "name": None,
             "function_call": {"name": "bash", "arguments": "{\"command\": \"ls\"}"}, "metadata": {}},
            {"role": "function", "content": "file.py", "name": "bash", "function_call": None, "metadata": {}},
        ],
        "output": [[{"role": "assistant", "content": "final answer", "function_call": None}]],
        "metadata": {"unmatched": False},
    }
    return {
        "run_id": "342704",
        "metadata": {"labels": ["reward_hacking"], "manually_reviewed": True,
                     "run_source": "rl", "task_id": "mlm", "model": "claude", "public": True},
        "samples": [short, long],
    }


def test_docent_record_scrubbed_with_positive_control():
    raw = _o3_style_record()
    leaks_in_raw = find_forbidden_keys(raw)
    assert "violation_score" in leaks_in_raw and "scores" in leaks_in_raw, (
        "positive control failed: the detector cannot see forbidden keys in the raw archive, so a "
        "clean payload below would be vacuous"
    )
    run = docent_record_to_run(raw, "h001")
    payload = run_payload(run)
    assert run.metadata == {"haystack_id": "h001"}
    assert find_forbidden_keys(payload) == [], f"scrub leak: {find_forbidden_keys(payload)}"
    assert run.name == "h001"
    assert all(t.metadata == {} for t in run.transcripts)


def test_malt_record_scrubbed_and_normalized():
    raw = _malt_style_record()
    assert find_forbidden_keys(raw), "positive control failed on the raw MALT row"
    run = malt_record_to_run(raw, "h229")
    payload = run_payload(run)
    assert run.metadata == {"haystack_id": "h229"}
    assert find_forbidden_keys(payload) == [], f"scrub leak: {find_forbidden_keys(payload)}"
    messages = run.transcripts[0].messages
    # Frozen rule: longest-input sample (4 msgs) + its output => 5 messages, ending in the final answer.
    assert len(messages) == 5
    assert messages[-1].content == "final answer"
    tool_messages = [m for m in messages if m.role == "tool"]
    assert len(tool_messages) == 1 and tool_messages[0].function == "bash"
    assistant_calls = [m for m in messages if m.role == "assistant" and getattr(m, "tool_calls", None)]
    assert assistant_calls and assistant_calls[0].tool_calls[0].function == "bash"


def test_malt_tie_resolves_to_last_sample():
    raw = _malt_style_record()
    twin = json.loads(json.dumps(raw["samples"][1]))
    twin["output"] = [[{"role": "assistant", "content": "second twin wins", "function_call": None}]]
    raw["samples"] = [raw["samples"][1], twin]
    run = malt_record_to_run(raw, "h100")
    assert run.transcripts[0].messages[-1].content == "second twin wins"


def test_blind_render_excludes_even_haystack_metadata():
    token = "HAYSTACK_" + secrets.token_hex(8)
    run = docent_record_to_run(_o3_style_record(), token)
    blind_text = AgentRunView.from_agent_run(run, context_config=blind_run_context()).to_text()
    assert token not in blind_text, "metadata reached the judge-visible text under the blind config"
    included = AgentRunView.from_agent_run(
        run, context_config=AgentRunContextConfig(agent_run_metadata=INCLUDE_ALL_GLOB_FILTER)
    ).to_text()
    assert token in included, "positive control failed: include-all does not surface the metadata"


@pytest.mark.skipif(not (CORPUS_DIR / "haystack_v0.json").exists(), reason="corpus data not present")
def test_full_frozen_corpus_converts_clean():
    haystack = json.loads((CORPUS_DIR / "haystack_v0.json").read_text(encoding="utf-8"))
    runs = haystack["runs"]
    assert len(runs) == 229
    payloads = []
    for i, entry in enumerate(runs):
        raw = json.loads(
            (CORPUS_DIR / entry["source"] / "runs" / f"{entry['run_id']}.json").read_text(encoding="utf-8")
        )
        payloads.append(run_payload(record_to_run(entry["source"], raw, f"h{i + 1:03d}")))
    assert find_forbidden_keys(payloads) == [], f"corpus scrub leak: {find_forbidden_keys(payloads)}"
