"""Batch investigation (live): ingest N runs -> rubric eval -> oracle cross-tab anchor.

Requires DOCENT_API_KEY / DOCENT_DOMAIN. Run scripts/fetch_traces.py --n N first. Writes
data/results.json (collection URL, per-run rows, anchor stats, verdict) and prints the 2x2, the
estimands with intervals, the association, and the pre-registered verdict.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from docent_investigation.anchor import Row, compute_anchor, evaluate_decision
from docent_investigation.fidelity import label_fidelity
from docent_investigation.batch import build_runs, join_rows, load_records
from docent_investigation.docent_client import DocentClientAdapter, extract_verdicts
from docent_investigation.rubric import false_success_rubric
from docent_investigation.transform import load_oracle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--name", default="docent-investigation: false-success on SWE-bench Verified")
    parser.add_argument("--collection-id", default=None, help="resume an existing collection (skip ingest/eval)")
    parser.add_argument("--rubric-id", default=None, help="rubric id when resuming")
    args = parser.parse_args()

    data_dir = Path(args.data)
    adapter = DocentClientAdapter()

    if args.collection_id:
        collection_id = args.collection_id
        public_url = adapter.make_public(collection_id)
        rubric_id = args.rubric_id or adapter.list_rubric_ids(collection_id)[0]
        verdicts = extract_verdicts(adapter.read_run_state(collection_id, rubric_id))
        n_ingested = len(verdicts)
    else:
        records = load_records(data_dir, args.n)
        oracle = load_oracle(data_dir / "oracle_summary.json")
        runs = build_runs(records, oracle)
        collection_id = adapter.create_collection(args.name, f"N={len(runs)} OpenHands Verified runs")
        adapter.ingest(collection_id, runs)
        public_url = adapter.make_public(collection_id)
        rubric_id = adapter.create_rubric(collection_id, false_success_rubric())
        adapter.evaluate(collection_id, rubric_id, max_agent_runs=len(runs))
        print(f"public_url: {public_url}\nwaiting for {len(runs)} verdicts ...")
        verdicts = adapter.wait_for_verdicts(collection_id, rubric_id, expected=len(runs), timeout_s=1800)
        n_ingested = len(runs)

    rows = join_rows(adapter, collection_id, verdicts)
    stats = compute_anchor([Row(r["instance_id"], r["resolved"], r["rubric_label"]) for r in rows])
    decision = evaluate_decision(stats)
    fidelity = label_fidelity(rows)
    out = {
        "collection_url": public_url,
        "collection_id": collection_id,
        "rubric_id": rubric_id,
        "n_ingested": n_ingested,
        "n_verdicts": len(rows),
        "rows": rows,
        "anchor": stats.as_dict(),
        "decision": decision.as_dict(),
        "fidelity": fidelity.as_dict(),
    }
    (data_dir / "results.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    # Tracked, de-identified projection so the 2x2 recomputes cold-clone without the live judge
    # (data/ is gitignored). Single-writer: this script owns both files.
    labeled = [
        {k: r[k] for k in ("instance_id", "rubric_label", "oracle_label", "resolved", "explanation")}
        for r in rows
    ]
    Path("reports/labeled_rows.json").write_text(
        json.dumps(labeled, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"\nverdicts: {len(rows)}/{n_ingested}")
    print(f"2x2  declared/resolved={stats.a_declared_resolved}  declared/unresolved={stats.b_declared_unresolved}"
          f"  notdecl/resolved={stats.c_notdeclared_resolved}  notdecl/unresolved={stats.d_notdeclared_unresolved}")
    print(f"false_success_rate={stats.false_success_rate}  95% CI={stats.false_success_rate_ci}"
          f"  declared_among_unresolved={stats.declared_among_unresolved}")
    print(f"resolved_rate declared={stats.resolved_rate_declared}  not_declared={stats.resolved_rate_not_declared}")
    print(f"association: fisher_p={stats.fisher_p:.4g}")
    print(f"VERDICT[{decision.primary_estimand} >= {decision.threshold:.2f}]={decision.verdict}  ({decision.rationale})")
    print(f"label-fidelity: judge_self_consistency={fidelity.judge_self_consistency} "
          f"(self-consistency only; human_agreement={fidelity.human_agreement})")
    print(f"saved -> {data_dir / 'results.json'}")


if __name__ == "__main__":
    main()
