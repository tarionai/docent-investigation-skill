"""Judge validation runner (offline): the pre-registered verdict on the judge itself.

Reads the two tracked artifacts — reports/labeled_rows.json (judge labels, written by
run_investigation.py) and reports/human_labels.json (blind human labels, written by label_runs.py) —
so a cold clone reproduces the result with no network and no data/ directory. Sole writer of
reports/judge_validation.json. Prints the judge-vs-human confusion matrix, each estimand with its
Wilson 95% interval, and the pre-registered precision verdict
(PRE_REGISTRATION_JUDGE_VALIDATION.md).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from docent_investigation.fidelity import label_fidelity
from docent_investigation.validation import (
    compute_validation,
    consensus_labels,
    evaluate_judge_decision,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--judge", default="reports/labeled_rows.json")
    parser.add_argument("--human", default="reports/human_labels.json")
    parser.add_argument("--out", default="reports/judge_validation.json")
    args = parser.parse_args()

    rows = json.loads(Path(args.judge).read_text(encoding="utf-8"))
    store = json.loads(Path(args.human).read_text(encoding="utf-8"))
    consensus, disagreements = consensus_labels(store["labels"])
    judge_labels = {r["instance_id"]: r["rubric_label"] for r in rows}

    v = compute_validation(judge_labels, consensus)
    decision = evaluate_judge_decision(v)
    fidelity = label_fidelity(rows, human_labels=consensus)
    out = {
        "protocol": store.get("protocol"),
        "raters": sorted({label["rater_id"] for label in store["labels"]}),
        "n_judge_rows": len(rows),
        "n_human_consensus": len(consensus),
        "disagreements_needing_adjudication": disagreements,
        "validation": v.as_dict(),
        "decision": decision.as_dict(),
        "fidelity": fidelity.as_dict(),
    }
    Path(args.out).write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"labeled overlap: {v.n_labeled}/{len(rows)} judge rows  raters={out['raters']}")
    print(f"confusion (positive={v.positive_label}): tp={v.tp} fp={v.fp} fn={v.fn} tn={v.tn}")
    print(f"precision={v.precision}  95% CI={v.precision_ci}")
    print(f"recall={v.recall}  95% CI={v.recall_ci}  f1={v.f1}")
    print(f"agreement={v.agreement}  cohen_kappa={v.cohen_kappa}")
    if disagreements:
        print(f"ADJUDICATION NEEDED for {len(disagreements)} instances: {disagreements}")
    print(f"VERDICT[{decision.primary_estimand} >= {decision.threshold:.2f}]={decision.verdict}"
          f"  ({decision.rationale})")
    print(f"saved -> {args.out}")


if __name__ == "__main__":
    main()
