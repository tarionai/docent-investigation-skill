import json
from unittest.mock import MagicMock

from docent.data_models.chat import AssistantMessage

from docent_investigation.batch import build_runs, join_rows, load_records
from docent_investigation.docent_client import Verdict
from docent_investigation.types import OracleLabel


def _record(instance_id: str) -> dict:
    return {
        "instance_id": instance_id,
        "history": [
            {"kind": "MessageEvent", "source": "assistant",
             "llm_message": {"content": [{"type": "text", "text": "All tests pass. Done."}]}}
        ],
    }


def test_build_runs_labels_from_oracle():
    oracle = {"a": OracleLabel.RESOLVED, "b": OracleLabel.UNRESOLVED}
    runs = build_runs([_record("a"), _record("b")], oracle)
    assert runs[0].metadata["scores"]["resolved"] is True
    assert runs[1].metadata["scores"]["resolved"] is False
    assert all(isinstance(r.transcripts[0].messages[0], AssistantMessage) for r in runs)


def test_join_rows_recovers_instance_and_oracle():
    adapter = MagicMock()
    adapter.get_run_metadata.side_effect = lambda cid, arid: {
        "ar-1": {"instance_id": "a", "oracle_label": "resolved"},
        "ar-2": {"instance_id": "b", "oracle_label": "unresolved"},
    }[arid]
    verdicts = [Verdict("ar-1", "declared_success", "x"), Verdict("ar-2", "not_declared", "y")]
    rows = join_rows(adapter, "col", verdicts)
    assert rows[0] == {"instance_id": "a", "oracle_label": "resolved", "resolved": True,
                       "rubric_label": "declared_success", "explanation": "x"}
    assert rows[1]["resolved"] is False


def test_load_records_reads_sorted(tmp_path):
    rec_dir = tmp_path / "records"
    rec_dir.mkdir()
    for iid in ("z_inst", "a_inst"):
        (rec_dir / f"{iid}.json").write_text(json.dumps(_record(iid)), encoding="utf-8")
    records = load_records(tmp_path, n=10)
    assert [r["instance_id"] for r in records] == ["a_inst", "z_inst"]  # sorted by filename
