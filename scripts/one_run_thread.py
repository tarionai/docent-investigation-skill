"""First vertical slice (live): ingest ONE real run -> rubric verdict + public collection URL.

Requires DOCENT_API_KEY / DOCENT_DOMAIN in the environment. Reads one fetched record from data/records/
(run scripts/fetch_traces.py first). Prints the public collection URL and the single false-success verdict.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from docent_investigation.docent_client import DocentClientAdapter
from docent_investigation.rubric import DEFAULT_JUDGE_MODEL, false_success_rubric
from docent_investigation.transform import load_oracle, openhands_record_to_agent_run


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data", help="dir holding records/ and oracle_summary.json")
    parser.add_argument("--name", default="docent-investigation: one-run slice")
    parser.add_argument("--model", default=DEFAULT_JUDGE_MODEL, help="judge model (provider/model_name)")
    args = parser.parse_args()

    data_dir = Path(args.data)
    record_path = sorted((data_dir / "records").glob("*.json"))[0]
    record = json.loads(record_path.read_text(encoding="utf-8"))
    oracle = load_oracle(data_dir / "oracle_summary.json")
    instance_id = record["instance_id"]
    run = openhands_record_to_agent_run(record, oracle=oracle.get(instance_id))

    adapter = DocentClientAdapter()
    collection_id = adapter.create_collection(args.name, f"one-run slice: {instance_id}")
    adapter.ingest(collection_id, [run])
    public_url = adapter.make_public(collection_id)
    adapter.set_plan_name("one-run false-success slice")
    _, verdicts = adapter.evaluate_rubric(
        collection_id, false_success_rubric(), model=args.model, max_agent_runs=1
    )

    print(f"instance_id     : {instance_id}")
    print(f"oracle          : {oracle.get(instance_id)}")
    print(f"public_url      : {public_url}")
    if verdicts:
        print(f"rubric_label    : {verdicts[0].label}")
        print(f"explanation     : {verdicts[0].explanation[:300]}")
    else:
        print("rubric_label    : <reading returned no usable verdict>")


if __name__ == "__main__":
    main()
