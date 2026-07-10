from unittest.mock import MagicMock

from docent.data_models.context_config import AgentRunContextConfig
from docent.data_models.metadata_util import EXCLUDE_ALL_GLOB_FILTER

from docent_investigation.docent_client import (
    DocentClientAdapter,
    Verdict,
    blind_run_context,
    verdicts_from_results,
)
from docent_investigation.rubric import RubricSpec

METADATA_SCOPES = (
    "agent_run_metadata",
    "transcript_group_metadata",
    "transcript_metadata",
    "message_metadata",
)


def _adapter():
    client = MagicMock()
    client.frontend_url = "https://docent.example"
    return client, DocentClientAdapter(client=client)


def _reading_result(run_id: str, label: str, explanation, error=None) -> dict:
    return {
        "id": f"rr-{run_id}",
        "arguments_dict": {"run": {"type": "agent_run", "id": run_id, "collection_id": "col-1"}},
        "output": {"label": label, "explanation": explanation},
        "error": error,
    }


def test_evaluate_rubric_keeps_judge_blind_to_oracle():
    client, adapter = _adapter()
    reading = client.read.return_value
    reading.id = "read-1"
    reading.results = [_reading_result("ar-1", "declared_success", "said 'all tests pass'")]
    rubric = RubricSpec(text="JUDGE THE RUN", output_schema={"type": "object"})

    reading_id, verdicts = adapter.evaluate_rubric(
        "col-1", rubric, model="openai/gpt-5.5", max_agent_runs=7
    )

    assert reading_id == "read-1"
    assert verdicts == [Verdict("ar-1", "declared_success", "said 'all tests pass'")]

    kwargs = client.read.call_args.kwargs
    config = kwargs["context_configs"]["run"]
    for scope in METADATA_SCOPES:
        assert getattr(config, scope) == EXCLUDE_ALL_GLOB_FILTER, f"{scope} is not exclude-all"
    assert kwargs["output_schema"] == {"type": "object"}
    assert kwargs["model"] == "openai/gpt-5.5"
    assert "JUDGE THE RUN" in kwargs["prompt_template"]

    dql = client.query.call_args.args[1]
    assert "LIMIT 7" in dql and "ORDER BY" in dql
    client.flush.assert_called_once_with(open_in_browser=False, auto_approve=True)


def test_sdk_default_context_still_excludes_metadata():
    """Tripwire: the SDK's own defaults must still exclude every metadata scope. The adapter pins the
    config explicitly, but the offline canary's default-render check depends on this staying true."""
    default = AgentRunContextConfig()
    blind = blind_run_context()
    for scope in METADATA_SCOPES:
        assert getattr(default, scope) == getattr(blind, scope), f"SDK default changed for {scope}"


def test_verdicts_from_results_parses_and_filters():
    class SdkResult:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    results = [
        _reading_result("ar-1", "declared_success", {"text": "cited 'the issue is fixed'"}),
        SdkResult(
            arguments_dict={"run": {"id": "ar-2", "collection_id": "col-1"}},
            output={"label": "not_declared", "explanation": "no completion claim"},
            error=None,
        ),
        _reading_result("ar-3", "declared_success", "boom", error="LLM refused"),
        {"arguments_dict": {"run": {"id": "ar-4"}}, "output": None, "error": None},
    ]
    assert verdicts_from_results(results) == [
        Verdict("ar-1", "declared_success", "cited 'the issue is fixed'"),
        Verdict("ar-2", "not_declared", "no completion claim"),
    ]


def test_verdicts_from_reading_uses_existing_results():
    client, adapter = _adapter()
    client.get_reading_results.return_value = [_reading_result("ar-9", "not_declared", "gave up")]
    verdicts = adapter.verdicts_from_reading("col-1", "read-9")
    client.get_reading_results.assert_called_once_with("col-1", "read-9")
    assert verdicts == [Verdict("ar-9", "not_declared", "gave up")]


def test_flush_retries_statement_timeout_then_succeeds(monkeypatch):
    monkeypatch.setattr("docent_investigation.docent_client.time.sleep", lambda _s: None)
    client, adapter = _adapter()
    client.flush.side_effect = [RuntimeError("HTTP 400: canceling statement due to statement timeout"), {"plan_id": "p1"}]
    assert adapter._flush_with_retry() == {"plan_id": "p1"}
    assert client.flush.call_count == 2


def test_flush_reraises_other_errors_immediately(monkeypatch):
    monkeypatch.setattr("docent_investigation.docent_client.time.sleep", lambda _s: None)
    client, adapter = _adapter()
    client.flush.side_effect = RuntimeError("HTTP 401: unauthorized")
    try:
        adapter._flush_with_retry()
        raise AssertionError("expected the non-timeout error to re-raise")
    except RuntimeError as error:
        assert "401" in str(error)
    assert client.flush.call_count == 1


def test_create_collection_and_public_url():
    client, adapter = _adapter()
    client.create_collection.return_value = "col-9"
    assert adapter.create_collection("name", "desc") == "col-9"
    client.create_collection.assert_called_once_with(name="name", description="desc")
    assert adapter.make_public("col-9") == "https://docent.example/dashboard/col-9"
    client.make_collection_public.assert_called_once_with("col-9")
