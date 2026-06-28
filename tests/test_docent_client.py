from unittest.mock import MagicMock

from docent_investigation.docent_client import DocentClientAdapter, Verdict, extract_verdicts


def _adapter():
    client = MagicMock()
    client.frontend_url = "https://docent.example"
    return client, DocentClientAdapter(client=client)


def test_evaluate_keeps_judge_blind_to_oracle():
    client, adapter = _adapter()
    client.start_rubric_eval_job.return_value = "job-1"
    job = adapter.evaluate("col-1", "rub-1", max_agent_runs=7)
    assert job == "job-1"
    client.start_rubric_eval_job.assert_called_once_with(
        "col-1", "rub-1", max_agent_runs=7, include_metadata=False
    )


def test_create_collection_and_public_url():
    client, adapter = _adapter()
    client.create_collection.return_value = "col-9"
    assert adapter.create_collection("name", "desc") == "col-9"
    client.create_collection.assert_called_once_with(name="name", description="desc")
    assert adapter.make_public("col-9") == "https://docent.example/dashboard/col-9"
    client.make_collection_public.assert_called_once_with("col-9")


def test_extract_verdicts_parses_run_state():
    state = {
        "results": [
            {
                "agent_run_id": "ar-1",
                "results": [
                    {"output": {"label": "declared_success",
                                "explanation": {"text": "said 'all tests pass'"}}}
                ],
            },
            {"agent_run_id": "ar-2", "results": [{"output": {"label": "not_declared",
                                                             "explanation": "no claim"}}]},
            {"agent_run_id": "ar-3", "results": []},  # not yet evaluated -> skipped
        ]
    }
    verdicts = extract_verdicts(state)
    assert verdicts == [
        Verdict("ar-1", "declared_success", "said 'all tests pass'"),
        Verdict("ar-2", "not_declared", "no claim"),
    ]


def test_wait_for_verdicts_returns_when_enough():
    client, adapter = _adapter()
    client.get_rubric_run_state.return_value = {
        "results": [{"agent_run_id": "ar-1",
                     "results": [{"output": {"label": "declared_success", "explanation": "x"}}]}]
    }
    verdicts = adapter.wait_for_verdicts("c", "r", expected=1, timeout_s=10, poll_s=1)
    assert len(verdicts) == 1 and verdicts[0].label == "declared_success"
