"""Pure transform: OpenHands SWE-bench trace records -> Docent AgentRun objects.

Side-effect-free. No network, no clock, no file writes (except `load_oracle`, which only reads).
The judge must stay blind to the oracle, so the rubric reading renders runs under an exclude-all
context config (docent_client.blind_run_context); the oracle is still stored in AgentRun.metadata
for the public collection UI and for the local cross-tab in N5.
"""

from __future__ import annotations

import json
from pathlib import Path

from docent.data_models import AgentRun, Transcript
from docent.data_models.agent_run import AgentRunView
from docent.data_models.chat import (
    AssistantMessage,
    ChatMessage,
    SystemMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)

from .docent_client import blind_run_context
from .types import OracleLabel


def _blocks_to_text(blocks: object) -> str:
    """Flatten an OpenHands content value to text.

    Handles a plain string, a single content-block dict ({text: ...}), or a list of such blocks.
    """
    if isinstance(blocks, str):
        return blocks
    if isinstance(blocks, dict):
        return blocks.get("text", "") or ""
    if isinstance(blocks, list):
        parts = [_blocks_to_text(b) for b in blocks]
        return "\n".join(p for p in parts if p)
    return ""


def _action_to_message(event: dict) -> AssistantMessage:
    action = event.get("action") or {}
    tool_name = event.get("tool_name") or action.get("kind") or "tool"
    args = {k: v for k, v in action.items() if k != "kind"}
    tool_call = ToolCall(id=event.get("tool_call_id") or "tc", function=tool_name, arguments=args)
    return AssistantMessage(content=_blocks_to_text(event.get("thought")), tool_calls=[tool_call])


def _observation_to_message(event: dict) -> ToolMessage:
    obs = event.get("observation") or {}
    error = {"is_error": True} if obs.get("is_error") else None
    return ToolMessage(
        content=_blocks_to_text(obs.get("content")) or "(no output)",
        tool_call_id=event.get("tool_call_id") or "tc",
        function=event.get("tool_name") or "tool",
        error=error,
    )


def _event_to_message(event: dict) -> ChatMessage | None:
    """Map one OpenHands history event to a Docent ChatMessage, or None to drop it."""
    kind = event.get("kind")
    if kind == "SystemPromptEvent":
        return SystemMessage(content=_blocks_to_text(event.get("system_prompt")) or "(system prompt)")
    if kind == "MessageEvent":
        text = _blocks_to_text((event.get("llm_message") or {}).get("content"))
        if not text:
            return None
        return UserMessage(content=text) if event.get("source") == "user" else AssistantMessage(content=text)
    if kind == "ActionEvent":
        return _action_to_message(event)
    if kind == "ObservationEvent":
        return _observation_to_message(event)
    return None


def openhands_record_to_agent_run(record: dict, oracle: OracleLabel | None = None) -> AgentRun:
    """Convert one OpenHands output.jsonl record into a Docent AgentRun (one transcript)."""
    instance_id = record.get("instance_id") or "unknown"
    messages = [m for m in (_event_to_message(e) for e in record.get("history") or []) if m is not None]
    if not messages:
        raise ValueError(f"no messages parsed from history for instance {instance_id!r}")
    metadata: dict[str, object] = {
        "instance_id": instance_id,
        "source": "pankajmathur/nemotron-nano-swebench-verified-traj (openhands)",
    }
    if oracle is not None:
        metadata["oracle_label"] = oracle.value
        metadata["scores"] = {"resolved": oracle.is_resolved}
    return AgentRun(
        name=instance_id,
        transcripts=[Transcript(name=instance_id, messages=messages, metadata={})],
        metadata=metadata,
    )


def record_to_blind_text(record: dict) -> str:
    """Render one raw trace record exactly as the blind judge sees it, for a human rater.

    The run is built WITHOUT an oracle argument, so no oracle field exists to leak, and it renders
    under the same pinned exclude-all context config the judge reading uses. The rater therefore
    reads the identical text the judge judged — nothing more.
    """
    run = openhands_record_to_agent_run(record)
    return AgentRunView.from_agent_run(run, context_config=blind_run_context()).to_text()


def load_oracle(summary_path: str | Path) -> dict[str, OracleLabel]:
    """Read an openhands.eval_output.swebench.json summary into instance_id -> OracleLabel."""
    data = json.loads(Path(summary_path).read_text(encoding="utf-8"))
    labels: dict[str, OracleLabel] = {}
    for instance_id in data.get("resolved_ids", []):
        labels[instance_id] = OracleLabel.RESOLVED
    for instance_id in data.get("empty_patch_ids", []):
        labels.setdefault(instance_id, OracleLabel.EMPTY_PATCH)
    for instance_id in data.get("unresolved_ids", []):
        labels.setdefault(instance_id, OracleLabel.UNRESOLVED)
    return labels
