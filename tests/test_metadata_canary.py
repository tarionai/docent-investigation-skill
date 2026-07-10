"""Canary (M1): prove the resolution oracle in AgentRun.metadata never reaches the judge.

The non-circularity guarantee rests on the judge being blind to the oracle, which is stored at
metadata.scores.resolved (see transform.openhands_record_to_agent_run). The judge runs as a Docent
reading whose agent_run parameter is rendered under an exclude-all context config
(docent_client.blind_run_context). Two complementary checks:

1. test_oracle_excluded_from_judge_text (OFFLINE, deterministic): renders the agent run exactly as the
   judge sees it (docent's own AgentRunView.to_text). Under the default context config every metadata
   filter is EXCLUDE_ALL, so a sentinel planted in metadata.scores is absent from the judge text; under
   an explicit include-all filter it appears. The include-all case is the positive control — without it
   the exclusion result would be vacuous. This proves the guarantee at the layer that actually builds
   the prompt, with no network and no LLM.

2. test_server_honors_oracle_exclusion (LIVE, billable; skipped without DOCENT_API_KEY): one run carries
   two sentinels — one in a user MESSAGE (always visible to the judge) and one in metadata.scores. After
   a real reading evaluated through adapter.evaluate_rubric (blind context config), the message sentinel
   MUST appear in the verdict (the judge echoes what it can see — the live positive control) and the
   metadata sentinel MUST NOT. That the judge surfaces the visible one but not the metadata one is direct
   end-to-end evidence the server does not feed metadata.scores to the judge.

The exclusion is structural twice over: exclude-all is both the SDK default (guarded by
test_sdk_default_context_still_excludes_metadata) and pinned explicitly by the adapter, where it enters
the reading's content hash — weakening it produces a different reading, not a silent leak.
"""

from __future__ import annotations

import os
import secrets

import pytest

from docent.data_models import AgentRun, Transcript
from docent.data_models.agent_run import AgentRunView
from docent.data_models.chat import AssistantMessage, UserMessage
from docent.data_models.context_config import AgentRunContextConfig
from docent.data_models.metadata_util import INCLUDE_ALL_GLOB_FILTER

from docent_investigation.docent_client import DocentClientAdapter
from docent_investigation.rubric import DEFAULT_JUDGE_MODEL, RubricSpec


def _run_with_oracle_sentinel(oracle_token: str, content_token: str | None = None) -> AgentRun:
    """An agent run whose oracle (in metadata.scores) carries a sentinel; optionally a second sentinel
    embedded in visible message content."""
    user_text = "Please fix the bug in the module."
    if content_token is not None:
        user_text += f" (ticket {content_token})"
    return AgentRun(
        name="oracle-canary",
        transcripts=[
            Transcript(
                name="canary",
                messages=[
                    UserMessage(content=user_text),
                    AssistantMessage(content="I examined the code and made a change."),
                ],
                metadata={},
            )
        ],
        metadata={"instance_id": "oracle-canary", "scores": {"resolved": True, "canary": oracle_token}},
    )


def test_oracle_excluded_from_judge_text():
    """Deterministic: the oracle sentinel is absent from judge-visible text under the default config and
    present only when metadata is explicitly included (the positive control)."""
    token = "ORACLE_" + secrets.token_hex(8)
    run = _run_with_oracle_sentinel(token)

    default_text = AgentRunView.from_agent_run(run).to_text()
    assert token not in default_text, (
        f"the oracle sentinel leaked into the default judge text -- metadata.scores is NOT excluded: "
        f"{default_text!r}"
    )

    included_text = AgentRunView.from_agent_run(
        run, context_config=AgentRunContextConfig(agent_run_metadata=INCLUDE_ALL_GLOB_FILTER)
    ).to_text()
    assert token in included_text, (
        "positive control failed: even with agent_run_metadata=INCLUDE_ALL the sentinel is absent, so "
        "the exclusion check above would be vacuous"
    )


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


@pytest.mark.skipif(not os.environ.get("DOCENT_API_KEY"), reason="live canary needs DOCENT_API_KEY")
def test_server_honors_oracle_exclusion():
    """End-to-end: after a real reading under the blind context config, the judge echoes the
    message-content sentinel (proving it cooperates) but never the metadata.scores sentinel (the
    guarantee)."""
    oracle_token = "CANARY_meta_" + secrets.token_hex(8)
    content_token = "CANARY_msg_" + secrets.token_hex(8)
    run = _run_with_oracle_sentinel(oracle_token, content_token=content_token)

    adapter = DocentClientAdapter()
    cid = adapter.create_collection("m1-oracle-canary", "M1 oracle-exclusion canary")
    adapter.ingest(cid, [run])
    adapter.set_plan_name("m1-oracle-canary")
    _, verdicts = adapter.evaluate_rubric(
        cid,
        RubricSpec(text=CANARY_RUBRIC_TEXT, output_schema=CANARY_SCHEMA),
        model=DEFAULT_JUDGE_MODEL,
        max_agent_runs=1,
    )
    assert verdicts, "no verdict returned"
    text = " ".join(f"{v.label} {v.explanation}" for v in verdicts)

    # Positive control: the judge can and does echo a sentinel it is allowed to see (message content).
    assert content_token in text, (
        f"positive control failed: the judge did not surface the message-content sentinel "
        f"({text!r}); a clean negative below would not be trustworthy"
    )
    # The guarantee: the oracle sentinel in metadata.scores must never reach the judge.
    assert oracle_token not in text, (
        f"LEAK: the metadata.scores oracle sentinel surfaced in the judge output -- non-circularity is "
        f"broken: {text!r}"
    )
