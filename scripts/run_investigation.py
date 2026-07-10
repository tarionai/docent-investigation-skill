"""Batch investigation (live): ingest N runs -> blind rubric reading -> oracle cross-tab anchor.

Requires DOCENT_API_KEY / DOCENT_DOMAIN. Run scripts/fetch_traces.py --n N first. Writes
data/results.json (collection URL, per-run rows, anchor stats, verdict) and prints the 2x2, the
estimands with intervals, the association, and the pre-registered verdict.

Resume: --collection-id skips ingest and re-submits the reading (content-addressed, so an identical
rubric/model over the same runs is a free cache hit); --collection-id + --reading-id fetches the
existing results without submitting a new plan.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from docent_investigation.anchor import Row, compute_anchor, evaluate_decision
from docent_investigation.fidelity import label_fidelity
from docent_investigation.batch import build_runs, join_rows, load_records
from docent_investigation.docent_client import DocentClientAdapter
from docent_investigation.rubric import DEFAULT_JUDGE_MODEL, false_success_rubric
from docent_investigation.transform import load_oracle


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--name", default="docent-investigation: false-success on SWE-bench Verified")
    parser.add_argument("--model", default=DEFAULT_JUDGE_MODEL, help="judge model (provider/model_name)")
    parser.add_argument("--collection-id", default=None, help="reuse an existing collection (skip ingest)")
    parser.add_argument("--reading-id", default=None, help="fetch existing reading results when resuming")
    args = parser.parse_args()

    data_dir = Path(args.data)
    adapter = DocentClientAdapter()
    adapter.set_plan_name("false-success rubric anchor")

    if args.collection_id:
        collection_id = args.collection_id
        public_url = adapter.make_public(collection_id)
        n_ingested = args.n
    else:
        records = load_records(data_dir, args.n)
        oracle = load_oracle(data_dir / "oracle_summary.json")
        runs = build_runs(records, oracle)
        collection_id = adapter.create_collection(args.name, f"N={len(runs)} OpenHands Verified runs")
        adapter.ingest(collection_id, runs)
        public_url = adapter.make_public(collection_id)
        n_ingested = len(runs)

    if args.reading_id:
        if not args.collection_id:
            parser.error("--reading-id requires --collection-id")
        reading_id = args.reading_id
        verdicts = adapter.verdicts_from_reading(collection_id, reading_id)
    else:
        print(f"public_url: {public_url}\nsubmitting blind rubric reading for {n_ingested} runs ...")
        reading_id, verdicts = adapter.evaluate_rubric(
            collection_id, false_success_rubric(), model=args.model, max_agent_runs=n_ingested
        )

    rows = join_rows(adapter, collection_id, verdicts)
    stats = compute_anchor([Row(r["instance_id"], r["resolved"], r["rubric_label"]) for r in rows])
    decision = evaluate_decision(stats)
    fidelity = label_fidelity(rows)
    out = {
        "collection_url": public_url,
        "collection_id": collection_id,
        "reading_id": reading_id,
        "judge_model": args.model,
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
