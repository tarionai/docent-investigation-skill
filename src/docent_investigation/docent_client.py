"""Thin typed adapter over the Docent SDK — the ONLY module that performs network I/O.

Callers see a small, stable surface and never touch raw SDK responses. The single most important
invariant lives here: rubric evaluation runs with include_metadata=False so the judge stays blind to
the oracle stored in AgentRun.metadata.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from docent.data_models import AgentRun
from docent.judges.types import Rubric


@dataclass(frozen=True)
class Verdict:
    agent_run_id: str
    label: str
    explanation: str


class DocentClientAdapter:
    def __init__(self, client: object | None = None) -> None:
        if client is None:
            from docent import Docent  # imported lazily so unit tests need no network

            client = Docent()
        self._client = client

    @property
    def frontend_url(self) -> str:
        return getattr(self._client, "frontend_url", "")

    def create_collection(self, name: str, description: str = "") -> str:
        return self._client.create_collection(name=name, description=description)

    def ingest(self, collection_id: str, runs: list[AgentRun]) -> dict:
        return self._client.add_agent_runs(collection_id, runs)

    def make_public(self, collection_id: str) -> str:
        self._client.make_collection_public(collection_id)
        return self.collection_url(collection_id)

    def create_rubric(self, collection_id: str, rubric: Rubric) -> str:
        return self._client.create_rubric(collection_id, rubric)

    def evaluate(self, collection_id: str, rubric_id: str, max_agent_runs: int | None = None) -> str:
        # include_metadata=False: the judge must NOT see the oracle in AgentRun.metadata.
        return self._client.start_rubric_eval_job(
            collection_id, rubric_id, max_agent_runs=max_agent_runs, include_metadata=False
        )

    def read_run_state(self, collection_id: str, rubric_id: str) -> dict:
        return self._client.get_rubric_run_state(collection_id, rubric_id)

    def get_run_metadata(self, collection_id: str, agent_run_id: str) -> dict:
        run = self._client.get_agent_run(collection_id, agent_run_id)
        meta = getattr(run, "metadata", None)
        if meta is None and isinstance(run, dict):
            meta = run.get("metadata")
        return meta or {}

    def list_rubric_ids(self, collection_id: str) -> list[str]:
        rubrics = self._client.list_rubrics(collection_id) or []
        return [r["id"] if isinstance(r, dict) else getattr(r, "id") for r in rubrics]

    def collection_url(self, collection_id: str) -> str:
        return f"{self.frontend_url}/dashboard/{collection_id}"

    def wait_for_verdicts(
        self, collection_id: str, rubric_id: str, expected: int, timeout_s: int = 600, poll_s: int = 5
    ) -> list[Verdict]:
        """Poll until at least `expected` results land (or timeout), then return parsed verdicts."""
        waited = 0
        state: dict = {}
        while waited < timeout_s:
            state = self.read_run_state(collection_id, rubric_id)
            if len(extract_verdicts(state)) >= expected:
                break
            time.sleep(poll_s)
            waited += poll_s
        return extract_verdicts(state)


def extract_verdicts(state: dict) -> list[Verdict]:
    """Flatten a rubric run-state into one Verdict per agent run (first rollout)."""
    verdicts: list[Verdict] = []
    for entry in state.get("results", []) or []:
        rollouts = entry.get("results") or []
        if not rollouts:
            continue
        output = rollouts[0].get("output") or {}
        explanation = output.get("explanation")
        if isinstance(explanation, dict):
            explanation = explanation.get("text", "")
        verdicts.append(
            Verdict(
                agent_run_id=entry.get("agent_run_id", ""),
                label=output.get("label", ""),
                explanation=explanation or "",
            )
        )
    return verdicts
