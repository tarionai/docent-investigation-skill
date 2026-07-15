"""Pure transform: Gap 3 archived haystack records -> scrubbed, blinded Docent AgentRuns.

Implements the allowlist frozen in PRE_REGISTRATION_BASELINE_RECALL.md: per message only
role/content (+ tool_calls for assistant, + tool_call_id/function/error for tool); AgentRun
metadata is exactly {"haystack_id": ...}; transcript and message metadata stay empty. Everything
else in the archives -- grader fields, scores, labels, model names, instance ids -- is
label-bearing or stratum-revealing and never enters the ingest payload. Side-effect-free: no
network, no clock, no file access.
"""

from __future__ import annotations

import json

from docent.data_models import AgentRun, Transcript
from docent.data_models.chat import (
    AssistantMessage,
    ChatMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)

# Frozen deny-list used ONLY to verify the allowlist output (never to drive scrubbing): any of
# these appearing as a non-null JSON key in the ingest payload is a leak and aborts the run.
FORBIDDEN_KEYS = frozenset(
    {
        "violation_score", "violation_type", "grader_response", "grader_system_prompt",
        "regraded", "additional_metadata", "scores", "attack_type", "epoch_id",
        "model", "model_name", "resolved", "instance_id", "turns", "api_calls",
        "tokens_sent", "tokens_received", "instance_cost", "swe_rex_version",
        "swe_agent_version", "labels", "manually_reviewed", "run_source", "task_id",
        "run_id",
    }
)

DOCENT_ARCHIVE_SOURCES = ("transluce_o3", "swebench_bashonly", "swebench_pro")


def find_forbidden_keys(payload: object) -> list[str]:
    """Recursively collect forbidden dict keys with non-null values anywhere in a payload."""
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in FORBIDDEN_KEYS and value is not None:
                    found.add(key)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return sorted(found)


def run_payload(run: AgentRun) -> dict:
    """The run exactly as serialized for upload (exclude_none so unset SDK fields don't count)."""
    return run.model_dump(mode="json", exclude_none=True)


def _flatten_content(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return value.get("text", "") or ""
    if isinstance(value, list):
        parts = [_flatten_content(v) for v in value]
        return "\n".join(p for p in parts if p)
    return ""


def _tool_calls(raw: object) -> list[ToolCall] | None:
    if not isinstance(raw, list) or not raw:
        return None
    calls = []
    for i, tc in enumerate(raw):
        args = tc.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {"raw": args}
        calls.append(ToolCall(id=str(tc.get("id") or f"tc{i}"), function=str(tc.get("function") or "tool"),
                              arguments=args if isinstance(args, dict) else {}))
    return calls


def _docent_message(msg: dict) -> ChatMessage:
    """Allowlist one archived Docent message: role/content (+tool fields); drop all else."""
    role = msg.get("role")
    content = _flatten_content(msg.get("content"))
    if role == "system":
        return SystemMessage(content=content)
    if role == "user":
        return UserMessage(content=content)
    if role == "assistant":
        return AssistantMessage(content=content, tool_calls=_tool_calls(msg.get("tool_calls")))
    if role == "tool":
        error = msg.get("error")
        return ToolMessage(
            content=content or "(no output)",
            tool_call_id=str(msg.get("tool_call_id") or "tc"),
            function=msg.get("function"),
            error=error if isinstance(error, dict) else None,
        )
    raise ValueError(f"unsupported archived message role: {role!r}")


def docent_record_to_run(record: dict, haystack_id: str) -> AgentRun:
    """Convert one archived Docent run JSON (o3 / bash-only / Pro) into a scrubbed AgentRun."""
    transcripts = []
    for i, t in enumerate(record.get("transcripts") or []):
        messages = [_docent_message(m) for m in t.get("messages") or []]
        if messages:
            transcripts.append(Transcript(name=f"t{i + 1}", messages=messages, metadata={}))
    if not transcripts:
        raise ValueError(f"no messages parsed for haystack id {haystack_id}")
    return AgentRun(name=haystack_id, transcripts=transcripts, metadata={"haystack_id": haystack_id})


def _malt_pick_sample(samples: list[dict]) -> dict:
    """Frozen rule: the sample with the longest input; ties resolved to the LAST such sample."""
    best = samples[0]
    for sample in samples[1:]:
        if len(sample.get("input") or []) >= len(best.get("input") or []):
            best = sample
    return best


def _malt_message(msg: dict, tool_counter: list[int]) -> ChatMessage:
    role = msg.get("role")
    content = _flatten_content(msg.get("content"))
    if role == "system":
        return SystemMessage(content=content)
    if role == "user":
        return UserMessage(content=content)
    if role == "assistant":
        call = msg.get("function_call")
        calls = None
        if isinstance(call, dict) and call.get("name"):
            tool_counter[0] += 1
            args = call.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {"raw": args}
            calls = [ToolCall(id=f"tc{tool_counter[0]}", function=str(call["name"]),
                              arguments=args if isinstance(args, dict) else {})]
        return AssistantMessage(content=content, tool_calls=calls)
    if role == "function":
        return ToolMessage(content=content or "(no output)", tool_call_id=f"tc{tool_counter[0]}",
                           function=msg.get("name"))
    raise ValueError(f"unsupported MALT message role: {role!r}")


def malt_record_to_run(record: dict, haystack_id: str) -> AgentRun:
    """Normalize one MALT row (cumulative per-call samples) into a single scrubbed transcript."""
    samples = record.get("samples") or []
    if not samples:
        raise ValueError(f"MALT row has no samples for haystack id {haystack_id}")
    chosen = _malt_pick_sample(samples)
    raw_messages = list(chosen.get("input") or [])
    output = chosen.get("output")
    if isinstance(output, list) and output and isinstance(output[0], list):
        raw_messages.extend(output[0])
    tool_counter = [0]
    messages = [_malt_message(m, tool_counter) for m in raw_messages]
    if not messages:
        raise ValueError(f"no messages parsed for haystack id {haystack_id}")
    return AgentRun(
        name=haystack_id,
        transcripts=[Transcript(name="t1", messages=messages, metadata={})],
        metadata={"haystack_id": haystack_id},
    )


def record_to_run(source: str, record: dict, haystack_id: str) -> AgentRun:
    """Dispatch one archived record to its source-specific scrubbing converter."""
    if source in DOCENT_ARCHIVE_SOURCES:
        return docent_record_to_run(record, haystack_id)
    if source == "malt":
        return malt_record_to_run(record, haystack_id)
    raise ValueError(f"unknown haystack source: {source!r}")
