"""Compute the pre-registered extras-adjudication results from the blind label store.

Implements only what PRE_REGISTRATION_EXTRAS_ADJUDICATION.md froze: per-stratum true-positive
rates with Wilson 95% intervals, the post-stratified pooled rate, boundary verdicts for the
escape hatch, and the descriptive tables (mapper agreement, post-reveal dispositions, label
distribution, EA-A1 footnote). Writes reports/extras_adjudication_results.json. Terminal output
is deliberately minimal -- coverage and boundary verdicts only -- so that if the escape hatch
triggers an extension, the rater is not anchored by detailed rates before labeling the extension
runs. With --update-queue (only after the sample is final: it changes the queue file, breaking
the sha pin the adjudication CLI verifies) it writes each sampled item's adjudicated status.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from docent_investigation.gap3_extras import (
    BEHAVIOR_CLASSES,
    CENSUS_SOURCES,
    DECISION_BOUNDARY,
    LABEL_UNSURE,
    PROTOCOL,
    boundary_verdict,
    pooled_tp_estimate,
    stratum_tp_stats,
)

ADJACENT_PAIR = {"evaluation_gaming", "reward_hacking"}
STATUS_BY_KIND = {"tp": "ed_confirmed_pending_second_rater", "other_concern": "ed_adjudicated_other_concern",
                  "none": "ed_adjudicated_none", "unsure": "ed_adjudicated_unsure"}


def _label_kind(label: str) -> str:
    return "tp" if label in BEHAVIOR_CLASSES else label if label in STATUS_BY_KIND else "unsure"


def _join(store: dict, sample: dict, queue: list[dict], rater: str) -> list[dict]:
    """One row per sampled run: stratum + blind label + judge fields + post-reveal."""
    by_label = {e["haystack_id"]: e for e in store["labels"] if e["rater_id"] == rater}
    by_queue = {e["haystack_id"]: e for e in queue}
    rows = []
    for info in sample["sampled"]:
        hid = info["haystack_id"]
        label_entry = by_label.get(hid)
        rows.append({
            "haystack_id": hid, "source": info["source"],
            "blind_label": label_entry["label"] if label_entry else None,
            "mapper_class": by_queue[hid]["mapped_class"],
            "post_reveal": label_entry.get("post_reveal") if label_entry else None,
            "order_index": label_entry.get("order_index") if label_entry else None,
        })
    return rows


def _per_stratum(rows: list[dict]) -> dict[str, dict]:
    out = {}
    for source in sorted({r["source"] for r in rows}):
        labels = [r["blind_label"] for r in rows if r["source"] == source and r["blind_label"]]
        stats = stratum_tp_stats(labels)
        if source in CENSUS_SOURCES:
            stats["boundary_verdict"] = ("undefined" if stats["rate"] is None else
                                         "above" if stats["rate"] > DECISION_BOUNDARY else "below")
            stats["boundary_basis"] = "census: exact stratum rate, no interval, no extension"
        else:
            stats["boundary_verdict"] = boundary_verdict(stats["wilson_95"])
            stats["boundary_basis"] = f"Wilson 95% vs {DECISION_BOUNDARY}"
        stats["label_distribution"] = dict(Counter(labels))
        out[source] = stats
    return out


def _mapper_agreement(rows: list[dict]) -> dict:
    tp_rows = [r for r in rows if r["blind_label"] in BEHAVIOR_CLASSES]
    table = [{"haystack_id": r["haystack_id"], "source": r["source"],
              "blind_label": r["blind_label"], "mapper_class": r["mapper_class"],
              "agree": r["blind_label"] == r["mapper_class"],
              "adjacent_confusion": {r["blind_label"], r["mapper_class"]} == ADJACENT_PAIR}
             for r in tp_rows]
    return {"n_true_positive_rows": len(table),
            "n_agree": sum(1 for t in table if t["agree"]),
            "n_adjacent_confusions": sum(1 for t in table if t["adjacent_confusion"]),
            "rows": table}


def _post_reveal_summary(rows: list[dict]) -> dict:
    labeled = [r for r in rows if r["post_reveal"]]
    would = Counter(f"{r['blind_label']} -> {r['post_reveal']['would_have_labeled']}"
                    for r in labeled if r["post_reveal"]["would_have_labeled"])
    return {"dispositions": dict(Counter(r["post_reveal"]["disposition"] for r in labeled)),
            "would_have_labeled": dict(would),
            "notes": [{"haystack_id": r["haystack_id"], "note": r["post_reveal"]["note"]}
                      for r in labeled if r["post_reveal"]["note"]]}


def _ea_a1_footnote(rows: list[dict]) -> dict:
    first = next((r for r in rows if r["order_index"] == 0), None)
    if first is None:
        return {"note": "no run with order_index 0 found"}
    return {"haystack_id": first["haystack_id"], "blind_label": first["blind_label"],
            "ambiguous_none": first["blind_label"] == "none",
            "note": "labeled before Amendment EA-A1 added other_concern; a 'none' here is "
                    "ambiguous between clean and out-of-taxonomy"}


def _update_queue(queue_path: Path, rows: list[dict]) -> int:
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    status_by_id = {r["haystack_id"]: STATUS_BY_KIND[_label_kind(r["blind_label"])]
                    for r in rows if r["blind_label"]}
    changed = 0
    for entry in queue:
        if entry["haystack_id"] in status_by_id:
            entry["status"] = status_by_id[entry["haystack_id"]]
            changed += 1
    queue_path.write_text(json.dumps(queue, indent=2, ensure_ascii=False), encoding="utf-8")
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default="reports/extras_blind_labels.json")
    parser.add_argument("--sample", default="data/gap3_corpus_v0/extras_adjudication_sample.json")
    parser.add_argument("--queue", default="data/gap3_corpus_v0/adjudication_queue_baseline.json")
    parser.add_argument("--rater", default="ed")
    parser.add_argument("--out", default="reports/extras_adjudication_results.json")
    parser.add_argument("--update-queue", action="store_true",
                        help="write adjudicated statuses into the queue file (final step only: "
                             "changes the queue sha the adjudication CLI pins)")
    args = parser.parse_args()

    sample = json.loads(Path(args.sample).read_text(encoding="utf-8"))
    queue_sha = hashlib.sha256(Path(args.queue).read_bytes()).hexdigest()
    if not args.update_queue and queue_sha != sample["queue_sha256"]:
        sys.exit("queue sha256 mismatch: not the pinned queue -- aborting")
    queue = json.loads(Path(args.queue).read_text(encoding="utf-8"))
    store = json.loads(Path(args.store).read_text(encoding="utf-8"))
    rows = _join(store, sample, queue, args.rater)
    unlabeled = [r["haystack_id"] for r in rows if r["blind_label"] is None]
    per_stratum = _per_stratum(rows)
    results = {
        "protocol": PROTOCOL, "created_utc": datetime.now(timezone.utc).isoformat(),
        "rater": args.rater, "seed": sample["seed"], "queue_sha256": sample["queue_sha256"],
        "n_sampled": len(rows), "n_labeled": len(rows) - len(unlabeled),
        "unlabeled": unlabeled, "extensions": sample["extensions"],
        "per_stratum": per_stratum,
        "pooled": pooled_tp_estimate(per_stratum, sample["stratum_sizes"]),
        "mapper_agreement": _mapper_agreement(rows),
        "post_reveal": _post_reveal_summary(rows),
        "amendment_ea_a1_footnote": _ea_a1_footnote(rows),
        "row_table": [{k: r[k] for k in ("haystack_id", "source", "blind_label", "mapper_class")}
                      for r in rows],
    }
    Path(args.out).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"results -> {args.out}")
    print(f"coverage: {results['n_labeled']}/{results['n_sampled']} labeled; unlabeled: {unlabeled}")
    for source, stats in per_stratum.items():
        print(f"boundary verdict [{source}]: {stats['boundary_verdict']} ({stats['boundary_basis']})")
    if args.update_queue:
        print(f"queue statuses updated: {_update_queue(Path(args.queue), rows)} sampled items")


if __name__ == "__main__":
    main()
