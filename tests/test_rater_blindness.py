"""Canary: prove the human rater's view is exactly the judge's blind view — nothing more.

The judge-validation study treats blind human labels as ground truth, so its guarantee mirrors the
oracle canary: the rater must see the identical text the judge judged, with no oracle and no judge
output visible. Three checks: (1) parity — the rater render equals the blind judge render even when
the judge-side run carries an oracle sentinel, and the sentinel appears in neither; (2) positive
control — an include-all config DOES surface the sentinel, so the exclusion is non-vacuous;
(3) structural — the labeling CLI's source never references the judge's artifacts, so judge labels
cannot reach the rater's screen.
"""

from __future__ import annotations

import secrets
from pathlib import Path

from docent.data_models.agent_run import AgentRunView
from docent.data_models.context_config import AgentRunContextConfig
from docent.data_models.metadata_util import INCLUDE_ALL_GLOB_FILTER

from docent_investigation.docent_client import blind_run_context
from docent_investigation.transform import openhands_record_to_agent_run, record_to_blind_text
from docent_investigation.types import OracleLabel

REPO_ROOT = Path(__file__).resolve().parent.parent


def _record() -> dict:
    return {
        "instance_id": "rater-canary",
        "history": [
            {"kind": "MessageEvent", "source": "user",
             "llm_message": {"content": "Please fix the bug in the module."}},
            {"kind": "MessageEvent", "source": "agent",
             "llm_message": {"content": "I examined the code and made a change."}},
        ],
    }


def _judge_run_with_sentinel(token: str):
    run = openhands_record_to_agent_run(_record(), oracle=OracleLabel.RESOLVED)
    run.metadata["scores"]["canary"] = token
    return run


def test_rater_view_matches_blind_judge_view_and_excludes_oracle():
    token = "ORACLE_" + secrets.token_hex(8)
    rater_text = record_to_blind_text(_record())
    judge_text = AgentRunView.from_agent_run(
        _judge_run_with_sentinel(token), context_config=blind_run_context()
    ).to_text()
    assert token not in judge_text, "oracle sentinel leaked into the blind judge text"
    assert rater_text == judge_text, (
        "the rater's view differs from the blind judge view -- the parity guarantee is broken"
    )


def test_positive_control_include_all_surfaces_sentinel():
    token = "ORACLE_" + secrets.token_hex(8)
    included_text = AgentRunView.from_agent_run(
        _judge_run_with_sentinel(token),
        context_config=AgentRunContextConfig(agent_run_metadata=INCLUDE_ALL_GLOB_FILTER),
    ).to_text()
    assert token in included_text, (
        "positive control failed: include-all does not surface the sentinel, so the parity test "
        "above would be vacuous"
    )


def test_label_cli_source_never_touches_judge_artifacts():
    source = (REPO_ROOT / "scripts" / "label_runs.py").read_text(encoding="utf-8")
    for judge_artifact in ("labeled_rows", "results.json", "judge_validation"):
        assert judge_artifact not in source, (
            f"scripts/label_runs.py references {judge_artifact!r} -- the rater could see judge output"
        )
