"""Batch helpers: load fetched records, build oracle-labeled runs, join verdicts to oracle metadata.

Kept out of the script so it is unit-testable with a mocked adapter.
"""

from __future__ import annotations

import json
from pathlib import Path

from docent.data_models import AgentRun

from .docent_client import DocentClientAdapter, Verdict
from .transform import openhands_record_to_agent_run
from .types import OracleLabel


def load_records(data_dir: str | Path, n: int) -> list[dict]:
    paths = sorted((Path(data_dir) / "records").glob("*.json"))[:n]
    return [json.loads(p.read_text(encoding="utf-8")) for p in paths]


def build_runs(records: list[dict], oracle: dict[str, OracleLabel]) -> list[AgentRun]:
    return [openhands_record_to_agent_run(r, oracle=oracle.get(r["instance_id"])) for r in records]


def join_rows(adapter: DocentClientAdapter, collection_id: str, verdicts: list[Verdict]) -> list[dict]:
    """Recover each verdict's instance_id + oracle from the stored AgentRun metadata."""
    rows = []
    for verdict in verdicts:
        meta = adapter.get_run_metadata(collection_id, verdict.agent_run_id)
        oracle_label = meta.get("oracle_label")
        rows.append(
            {
                "instance_id": meta.get("instance_id", ""),
                "oracle_label": oracle_label,
                "resolved": oracle_label == "resolved",
                "rubric_label": verdict.label,
                "explanation": verdict.explanation,
            }
        )
    return rows
