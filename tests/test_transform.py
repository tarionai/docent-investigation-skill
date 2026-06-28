import json
from pathlib import Path

import pytest
from docent.data_models.chat import AssistantMessage, SystemMessage, ToolMessage

from docent_investigation.transform import (
    load_oracle,
    openhands_record_to_agent_run,
)
from docent_investigation.types import OracleLabel

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _record() -> dict:
    return json.loads((FIXTURES / "openhands_record.json").read_text(encoding="utf-8"))


def test_record_converts_to_agent_run_with_per_step_tool_calls():
    run = openhands_record_to_agent_run(_record())
    assert len(run.transcripts) == 1
    msgs = run.transcripts[0].messages
    assert any(isinstance(m, SystemMessage) for m in msgs)
    asst_with_tools = [m for m in msgs if isinstance(m, AssistantMessage) and m.tool_calls]
    assert asst_with_tools, "expected at least one assistant message carrying a tool call"
    assert asst_with_tools[0].tool_calls[0].function  # tool name present
    assert any(isinstance(m, ToolMessage) for m in msgs), "expected tool observation messages"
    assert run.metadata["instance_id"] == _record()["instance_id"]


def test_oracle_is_stored_only_when_provided():
    plain = openhands_record_to_agent_run(_record())
    assert "scores" not in plain.metadata  # judge stays blind unless we opt in

    labeled = openhands_record_to_agent_run(_record(), oracle=OracleLabel.UNRESOLVED)
    assert labeled.metadata["scores"]["resolved"] is False
    assert labeled.metadata["oracle_label"] == "unresolved"


def test_empty_history_raises():
    with pytest.raises(ValueError):
        openhands_record_to_agent_run({"instance_id": "x", "history": []})


def test_load_oracle_partitions_ids():
    labels = load_oracle(FIXTURES / "oracle_summary.json")
    summary = json.loads((FIXTURES / "oracle_summary.json").read_text(encoding="utf-8"))
    assert len(labels) == summary["total_instances"]
    a_resolved = summary["resolved_ids"][0]
    assert labels[a_resolved] is OracleLabel.RESOLVED
    assert labels[a_resolved].is_resolved is True
    an_empty = summary["empty_patch_ids"][0]
    assert labels[an_empty] is OracleLabel.EMPTY_PATCH
