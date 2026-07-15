"""Thin typed adapter over the Docent SDK — the ONLY module that performs network I/O.

Callers see a small, stable surface and never touch raw SDK responses. The single most important
invariant lives here: the rubric reading renders each agent run under an explicit exclude-all
context config, so the judge stays blind to the oracle stored in AgentRun.metadata. Context configs
are part of the reading's content hash, so weakening the config produces a visibly different reading
rather than a silent leak.

Built on the Readings API (client.query + client.read), Docent's recommended analysis surface; the
older rubric-eval job API is not used.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from docent.data_models import AgentRun
from docent.data_models.context_config import AgentRunContextConfig
from docent.data_models.metadata_util import EXCLUDE_ALL_GLOB_FILTER

from .rubric import RubricSpec

RUN_PARAM = "run"


@dataclass(frozen=True)
class Verdict:
    agent_run_id: str
    label: str
    explanation: str


def blind_run_context() -> AgentRunContextConfig:
    """Exclude-all on every metadata scope: nothing in AgentRun.metadata (where the oracle lives),
    transcript metadata, or message metadata is rendered for the judge. These are the SDK defaults,
    stated explicitly so the invariant is pinned by this repo, not by upstream defaults."""
    return AgentRunContextConfig(
        agent_run_metadata=EXCLUDE_ALL_GLOB_FILTER,
        transcript_group_metadata=EXCLUDE_ALL_GLOB_FILTER,
        transcript_metadata=EXCLUDE_ALL_GLOB_FILTER,
        message_metadata=EXCLUDE_ALL_GLOB_FILTER,
    )


class DocentClientAdapter:
    def __init__(self, client: object | None = None) -> None:
        if client is None:
            from docent import Docent  # imported lazily so unit tests need no network

            client = Docent()
        self._client = client

    @property
    def frontend_url(self) -> str:
        return getattr(self._client, "frontend_url", "")

    def set_plan_name(self, name: str) -> None:
        self._client.plan_name = name

    def create_collection(self, name: str, description: str = "") -> str:
        return self._client.create_collection(name=name, description=description)

    def ingest(self, collection_id: str, runs: list[AgentRun]) -> dict:
        return self._client.add_agent_runs(collection_id, runs)

    def make_public(self, collection_id: str) -> str:
        self._client.make_collection_public(collection_id)
        return self.collection_url(collection_id)

    def get_run_metadata(self, collection_id: str, agent_run_id: str) -> dict:
        run = self._client.get_agent_run(collection_id, agent_run_id)
        meta = getattr(run, "metadata", None)
        if meta is None and isinstance(run, dict):
            meta = run.get("metadata")
        return meta or {}

    def collection_url(self, collection_id: str) -> str:
        return f"{self.frontend_url}/dashboard/{collection_id}"

    def wait_until_queryable(self, collection_id: str, attempts: int = 40, delay_s: float = 10.0) -> None:
        """Block until a freshly ingested collection accepts DQL. The server's post-ingest warmup
        window (statement timeouts; 15-35s observed 2026-07-10, >6min observed 2026-07-15) breaks
        plan submission, so probe with a read-only query and only submit readings once it clears."""
        probe = "SELECT agent_runs.id AS run FROM agent_runs ORDER BY agent_runs.id LIMIT 1"
        for attempt in range(attempts):
            try:
                self._client.execute_dql(collection_id, probe)
                return
            except Exception as error:
                if "statement timeout" not in str(error) or attempt == attempts - 1:
                    raise
                time.sleep(delay_s)

    def evaluate_rubric(
        self,
        collection_id: str,
        rubric: RubricSpec,
        *,
        model: str,
        max_agent_runs: int | None = None,
        name: str = "Apply frozen rubric to each agent run",
        reasoning_effort: str | None = None,
    ) -> tuple[str, list[Verdict]]:
        """One reading step per agent run: query run ids, judge each under the blind context config,
        block until results land. Returns (reading_id, verdicts). Content-addressed: re-running the
        identical rubric/model/config over the same runs reuses cached results."""
        limit = f" LIMIT {int(max_agent_runs)}" if max_agent_runs else ""
        rows = self._client.query(
            collection_id,
            # ORDER BY keeps row order stable so the reading's cache identity is reproducible.
            f"SELECT agent_runs.id AS {RUN_PARAM} FROM agent_runs ORDER BY agent_runs.id{limit}",
            name=f"Select {max_agent_runs or 'all'} agent runs ordered by id",
        )
        extra = {"reasoning_effort": reasoning_effort} if reasoning_effort else {}
        reading = self._client.read(
            prompt_template=[getattr(rows, RUN_PARAM).as_type("agent_run"), rubric.text],
            context_configs={RUN_PARAM: blind_run_context()},
            output_schema=rubric.output_schema,
            model=model,
            name=name,
            **extra,
        )
        self._flush_with_retry()
        return reading.id, verdicts_from_results(reading.results)

    def evaluate_text_prompts(
        self,
        collection_id: str,
        prompts: list[str],
        *,
        output_schema: dict,
        model: str,
        name: str,
    ) -> tuple[str, list[dict]]:
        """Scripted reading over plain-text prompts (no transcript refs rendered). Used for the
        class mapper, whose input is investigator explanations only -- never the transcripts and
        never the manifest. Returns (reading_id, outputs); errored results are dropped."""
        reading = self._client.read(
            prompts_list=[[p] for p in prompts],
            output_schema=output_schema,
            model=model,
            name=name,
            collection_id=collection_id,
        )
        self._flush_with_retry()
        outputs = []
        for result in reading.results or []:
            output = _field(result, "output")
            if not _field(result, "error") and isinstance(output, dict):
                outputs.append(output)
        return reading.id, outputs

    def get_reading_results_raw(self, collection_id: str, reading_id: str) -> list[dict]:
        """Resume path for scripted readings: raw outputs of an existing reading."""
        outputs = []
        for result in self._client.get_reading_results(collection_id, reading_id) or []:
            output = _field(result, "output")
            if not _field(result, "error") and isinstance(output, dict):
                outputs.append(output)
        return outputs

    def _flush_with_retry(self, attempts: int = 10, delay_s: float = 20.0) -> object:
        """Headless flow: approve programmatically (implicit flushes never auto-approve). A freshly
        ingested collection's DQL hits the server's statement timeout for its first ~30s (observed
        2026-07-10; >60s observed 2026-07-15), so retry that specific error with a bounded backoff;
        anything else re-raises."""
        for attempt in range(attempts):
            try:
                return self._client.flush(open_in_browser=False, auto_approve=True)
            except Exception as error:
                if "statement timeout" not in str(error) or attempt == attempts - 1:
                    raise
                time.sleep(delay_s)

    def verdicts_from_reading(self, collection_id: str, reading_id: str) -> list[Verdict]:
        """Resume path: fetch an existing reading's results without submitting a new plan."""
        return verdicts_from_results(self._client.get_reading_results(collection_id, reading_id))


def _field(result: object, key: str) -> object:
    if isinstance(result, dict):
        return result.get(key)
    return getattr(result, key, None)


def verdicts_from_results(results: list) -> list[Verdict]:
    """Flatten reading results (SDK objects or dicts) into one Verdict per agent run, recovering the
    run id from the template argument. Errored / empty results are dropped."""
    verdicts: list[Verdict] = []
    for result in results or []:
        output = _field(result, "output")
        if _field(result, "error") or not isinstance(output, dict):
            continue
        arguments = _field(result, "arguments_dict") or _field(result, "arguments") or {}
        ref = (arguments.get(RUN_PARAM) if isinstance(arguments, dict) else None) or {}
        run_id = ref.get("id", "") if isinstance(ref, dict) else str(ref)
        explanation = output.get("explanation")
        if isinstance(explanation, dict):
            explanation = explanation.get("text", "")
        verdicts.append(
            Verdict(agent_run_id=run_id, label=output.get("label", ""), explanation=explanation or "")
        )
    return verdicts
