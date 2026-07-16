"""Gap 3 baseline recall (live): scrubbed blind ingest -> stock rubric reading -> offline scoring.

Executes PRE_REGISTRATION_BASELINE_RECALL.md (frozen at commit 40a9eef) end to end: verifies the
corpus freeze hashes, converts the 229-run haystack through the allowlist scrubber with blinded
ids, runs the live leak canary, ingests into ONE fresh private collection, submits the frozen
stock rubric reading, maps flagged explanations to behavior classes with the frozen mapper, and
scores recall offline against the withheld manifest (which is never uploaded or referenced in any
prompt). The shared live orchestration now lives in docent_investigation.gap3_pipeline (moved
verbatim after the baseline run at 48d4824, so step 4 reuses the identical path).

Resume: --collection-id skips canary+ingest; --reading-id fetches the existing stock verdicts;
--mapper-reading-id fetches existing mapper outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from docent_investigation.docent_client import DocentClientAdapter
from docent_investigation.gap3_baseline import (
    BASELINE_RUBRIC_TEXT,
    LABEL_MATCH,
    MAPPER_MODEL,
    STOCK_JUDGE_MODEL,
    STOCK_REASONING_EFFORT,
    baseline_rubric,
)
from docent_investigation.gap3_pipeline import (
    build_blind_runs,
    ingest_haystack,
    run_leak_canary,
    run_mapper,
    verdicts_by_haystack_id,
    verify_freeze,
)
from docent_investigation.gap3_scoring import (
    disputed_extras,
    flag_rates,
    near_misses,
    positive_rows,
    recall_summary,
)


def score_and_write(corpus: Path, blind_map: dict, verdict_by_hid: dict, class_by_hid: dict,
                    record: dict) -> None:
    manifest = json.loads((corpus / "manifest_v0.json").read_text(encoding="utf-8"))
    hid_by_run = {e["run_id"]: h for h, e in blind_map.items()}
    rows = positive_rows(manifest["positives"], hid_by_run, verdict_by_hid, class_by_hid)
    extras = disputed_extras(blind_map, {r["haystack_id"] for r in rows}, verdict_by_hid, class_by_hid)
    results = dict(
        record,
        created_utc=datetime.now(timezone.utc).isoformat(),
        n_verdicts=len(verdict_by_hid),
        coverage=len(verdict_by_hid) / len(blind_map),
        recall=recall_summary(rows),
        flag_rates=flag_rates(blind_map, verdict_by_hid),
        positive_rows=rows,
        near_misses=near_misses(rows),
        n_disputed_extras=len(extras),
    )
    Path("reports/baseline_recall_results.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (corpus / "adjudication_queue_baseline.json").write_text(
        json.dumps(extras, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print_summary(results)


def print_summary(results: dict) -> None:
    recall = results["recall"]
    overall = recall["overall"]["primary_class_matched"]
    print(f"\nverdicts: {results['n_verdicts']} (coverage {results['coverage']:.3f})")
    print(f"PRIMARY overall recall: {overall['successes']}/{overall['n']}"
          f" = {overall['estimate']:.3f}  wilson95={overall['wilson_95']}")
    for cls, block in recall["per_class"].items():
        p = block["primary_class_matched"]
        s = block["secondary_class_agnostic"]
        print(f"  {cls}: primary {p['successes']}/{p['n']} wilson95={p['wilson_95']}"
              f" | flagged {s['successes']}/{s['n']}")
    print(f"flag rate overall: {results['flag_rates']['overall']['estimate']:.3f}")
    print(f"disputed extras -> adjudication: {results['n_disputed_extras']}")
    print("saved -> reports/baseline_recall_results.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="data/gap3_corpus_v0")
    parser.add_argument("--collection-id", default=None, help="resume: skip canary + ingest")
    parser.add_argument("--reading-id", default=None, help="resume: fetch existing stock verdicts")
    parser.add_argument("--mapper-reading-id", default=None, help="resume: fetch mapper outputs")
    parser.add_argument("--canary-outcome", default="skipped (resumed collection)",
                        help="recorded canary outcome when resuming a collection")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    verify_freeze(corpus)
    runs, blind_map = build_blind_runs(corpus)
    (corpus / "blind_id_map.json").write_text(json.dumps(blind_map, indent=2), encoding="utf-8")

    # One fresh client per plan phase: a second flush on the same client dies with
    # "Reading plan not found" (observed 2026-07-15), so canary, stock reading, and mapper
    # each get their own adapter/plan.
    adapter = DocentClientAdapter()
    canary = {"outcome": args.canary_outcome}
    if args.collection_id:
        cid = args.collection_id
    else:
        canary = run_leak_canary(DocentClientAdapter(), STOCK_JUDGE_MODEL, STOCK_REASONING_EFFORT,
                                 "gap3 baseline leak canary", "gap3-baseline-canary")
        cid = ingest_haystack(adapter, runs, "gap3 baseline recall: haystack v0 (blind, scrubbed)",
                              f"N={len(runs)} scrubbed runs; blinded ids; private during study")
    print(f"collection: {adapter.collection_url(cid)} (private)")

    if args.reading_id:
        reading_id, verdicts = args.reading_id, adapter.verdicts_from_reading(cid, args.reading_id)
    else:
        reader = DocentClientAdapter()
        reader.set_plan_name("gap3 baseline recall: stock rubric blind over haystack v0")
        reader.wait_until_queryable(cid, attempts=60)
        reading_id, verdicts = reader.evaluate_rubric(
            cid, baseline_rubric(), model=STOCK_JUDGE_MODEL, max_agent_runs=len(runs),
            name="Stock rubric: flag concerning behavior (frozen baseline)",
            reasoning_effort=STOCK_REASONING_EFFORT,
        )
    verdict_by_hid = verdicts_by_haystack_id(adapter, cid, verdicts)
    flagged = {h: v for h, v in verdict_by_hid.items() if v["label"] == LABEL_MATCH}
    print(f"verdicts: {len(verdict_by_hid)}; flagged: {len(flagged)}")

    mapper_adapter = DocentClientAdapter()
    mapper_adapter.set_plan_name("gap3 baseline recall: class mapper")
    mapper_reading_id, class_by_hid = run_mapper(mapper_adapter, cid, flagged, args.mapper_reading_id)
    record = {
        "pre_registration": {"file": "PRE_REGISTRATION_BASELINE_RECALL.md", "commit": "40a9eef"},
        "collection_id": cid,
        "reading_id": reading_id,
        "mapper_reading_id": mapper_reading_id,
        "judge_model": STOCK_JUDGE_MODEL,
        "reasoning_effort": STOCK_REASONING_EFFORT,
        "mapper_model": MAPPER_MODEL,
        "rubric_sha256": hashlib.sha256(BASELINE_RUBRIC_TEXT.encode("utf-8")).hexdigest(),
        "canary": canary,
        "n_ingested": len(runs),
    }
    score_and_write(corpus, blind_map, verdict_by_hid, class_by_hid, record)


if __name__ == "__main__":
    main()
