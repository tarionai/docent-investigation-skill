"""Gap 3 step-4 recall (live): frozen checklist policy -> paired delta vs the measured baseline.

Executes PRE_REGISTRATION_STEP4_RECALL.md (frozen at commit b21c244) end to end: verifies the
corpus freeze hashes, converts the 229-run haystack through the same allowlist scrubber with the
same blinded ids, runs the live leak canary with the step-4 judge tier, ingests into ONE fresh
private collection, submits the frozen checklist-policy reading exactly once, maps flagged
explanations with the IDENTICAL frozen mapper, scores recall offline against the withheld
manifest, and computes the pre-registered paired delta (exact one-sided McNemar + precision gate)
against reports/baseline_recall_results.json. Extras go to a NEW queue file; the baseline queue
is never touched.

Resume: --collection-id skips canary+ingest; --reading-id fetches the existing policy verdicts;
--mapper-reading-id fetches existing mapper outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from docent_investigation.docent_client import DocentClientAdapter
from docent_investigation.gap3_baseline import LABEL_MATCH, MAPPER_MODEL
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
from docent_investigation.gap3_step4 import (
    BASELINE_FLAG_COUNT,
    POLICY_JUDGE_MODEL,
    POLICY_REASONING_EFFORT,
    POLICY_RUBRIC_TEXT,
    discordant_counts,
    headline_verdict,
    paired_rows,
    policy_rubric,
)

BASELINE_RESULTS_PATH = Path("reports/baseline_recall_results.json")
RESULTS_PATH = Path("reports/step4_recall_results.json")
EXTRAS_QUEUE_NAME = "adjudication_queue_step4.json"


def load_baseline_results() -> dict:
    """The measured baseline this study is paired against; refuse artifact/constant drift."""
    results = json.loads(BASELINE_RESULTS_PATH.read_text(encoding="utf-8"))
    flags = results["flag_rates"]["overall"]["successes"]
    if flags != BASELINE_FLAG_COUNT:
        sys.exit(f"BASELINE DRIFT: artifact flag count {flags} != frozen gate {BASELINE_FLAG_COUNT}")
    return results


def paired_analysis(baseline_results: dict, rows: list[dict], policy_flag_count: int) -> dict:
    """The pre-registered paired delta: discordant tables, McNemar, gate, headline verdict."""
    pairs = paired_rows(baseline_results["positive_rows"], rows)
    primary = discordant_counts(pairs, "baseline_recovered", "policy_recovered")
    secondary = discordant_counts(pairs, "baseline_flagged", "policy_flagged")
    return {
        "baseline_artifact": {"file": str(BASELINE_RESULTS_PATH),
                              "reading_id": baseline_results["reading_id"]},
        "pairs": pairs,
        "primary_discordant": primary,
        "secondary_discordant_class_agnostic": secondary,
        "headline": headline_verdict(primary, policy_flag_count),
    }


def score_and_write(corpus: Path, blind_map: dict, verdict_by_hid: dict, class_by_hid: dict,
                    record: dict) -> None:
    manifest = json.loads((corpus / "manifest_v0.json").read_text(encoding="utf-8"))
    hid_by_run = {e["run_id"]: h for h, e in blind_map.items()}
    rows = positive_rows(manifest["positives"], hid_by_run, verdict_by_hid, class_by_hid)
    extras = disputed_extras(blind_map, {r["haystack_id"] for r in rows}, verdict_by_hid, class_by_hid)
    rates = flag_rates(blind_map, verdict_by_hid)
    results = dict(
        record,
        created_utc=datetime.now(timezone.utc).isoformat(),
        n_verdicts=len(verdict_by_hid),
        coverage=len(verdict_by_hid) / len(blind_map),
        recall=recall_summary(rows),
        flag_rates=rates,
        positive_rows=rows,
        near_misses=near_misses(rows),
        n_disputed_extras=len(extras),
        paired=paired_analysis(load_baseline_results(), rows, rates["overall"]["successes"]),
    )
    RESULTS_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (corpus / EXTRAS_QUEUE_NAME).write_text(
        json.dumps(extras, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print_summary(results)


def print_summary(results: dict) -> None:
    """Aggregate counts only — never entry-level judge fields (standing EA-A2 rule)."""
    overall = results["recall"]["overall"]["primary_class_matched"]
    paired = results["paired"]
    primary, headline = paired["primary_discordant"], paired["headline"]
    print(f"\nverdicts: {results['n_verdicts']} (coverage {results['coverage']:.3f})")
    print(f"POLICY primary recall: {overall['successes']}/{overall['n']}"
          f" = {overall['estimate']:.3f}  wilson95={overall['wilson_95']}")
    for cls, block in results["recall"]["per_class"].items():
        p, s = block["primary_class_matched"], block["secondary_class_agnostic"]
        print(f"  {cls}: primary {p['successes']}/{p['n']} | flagged {s['successes']}/{s['n']}")
    print(f"discordant pairs: policy-only {primary['policy_only']},"
          f" baseline-only {primary['baseline_only']}, p={primary['p_one_sided']}")
    print(f"flag rate overall: {results['flag_rates']['overall']['estimate']:.3f}"
          f" (gate max {headline['gate_max_flags']}/229; holds: {headline['gate_holds']})")
    print(f"HEADLINE VERDICT: {headline['verdict']}")
    print(f"disputed extras -> new step-4 queue: {results['n_disputed_extras']}")
    print(f"saved -> {RESULTS_PATH}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="data/gap3_corpus_v0")
    parser.add_argument("--collection-id", default=None, help="resume: skip canary + ingest")
    parser.add_argument("--reading-id", default=None, help="resume: fetch existing policy verdicts")
    parser.add_argument("--mapper-reading-id", default=None, help="resume: fetch mapper outputs")
    parser.add_argument("--canary-outcome", default="skipped (resumed collection)",
                        help="recorded canary outcome when resuming a collection")
    args = parser.parse_args()

    corpus = Path(args.corpus)
    verify_freeze(corpus)
    load_baseline_results()  # fail fast on drift before any live call
    runs, blind_map = build_blind_runs(corpus)

    # One fresh client per plan phase (one flush per client, observed 2026-07-15).
    adapter = DocentClientAdapter()
    canary = {"outcome": args.canary_outcome}
    if args.collection_id:
        cid = args.collection_id
    else:
        canary = run_leak_canary(DocentClientAdapter(), POLICY_JUDGE_MODEL, POLICY_REASONING_EFFORT,
                                 "gap3 step4 leak canary", "gap3-step4-canary")
        cid = ingest_haystack(adapter, runs, "gap3 step4 recall: haystack v0 (blind, scrubbed)",
                              f"N={len(runs)} scrubbed runs; blinded ids; private during study")
    print(f"collection: {adapter.collection_url(cid)} (private)")

    if args.reading_id:
        reading_id, verdicts = args.reading_id, adapter.verdicts_from_reading(cid, args.reading_id)
    else:
        reader = DocentClientAdapter()
        reader.set_plan_name("gap3 step4 recall: checklist policy blind over haystack v0")
        reader.wait_until_queryable(cid, attempts=60)
        reading_id, verdicts = reader.evaluate_rubric(
            cid, policy_rubric(), model=POLICY_JUDGE_MODEL, max_agent_runs=len(runs),
            name="Checklist policy: flag misbehavior patterns (frozen step-4 treatment)",
            reasoning_effort=POLICY_REASONING_EFFORT,
        )
    verdict_by_hid = verdicts_by_haystack_id(adapter, cid, verdicts)
    flagged = {h: v for h, v in verdict_by_hid.items() if v["label"] == LABEL_MATCH}
    print(f"verdicts: {len(verdict_by_hid)}; flagged: {len(flagged)}")

    mapper_adapter = DocentClientAdapter()
    mapper_adapter.set_plan_name("gap3 step4 recall: class mapper (frozen, identical)")
    mapper_reading_id, class_by_hid = run_mapper(mapper_adapter, cid, flagged, args.mapper_reading_id)
    record = {
        "pre_registration": {"file": "PRE_REGISTRATION_STEP4_RECALL.md", "commit": "b21c244"},
        "collection_id": cid,
        "reading_id": reading_id,
        "mapper_reading_id": mapper_reading_id,
        "judge_model": POLICY_JUDGE_MODEL,
        "reasoning_effort": POLICY_REASONING_EFFORT,
        "mapper_model": MAPPER_MODEL,
        "rubric_sha256": hashlib.sha256(POLICY_RUBRIC_TEXT.encode("utf-8")).hexdigest(),
        "canary": canary,
        "n_ingested": len(runs),
    }
    score_and_write(corpus, blind_map, verdict_by_hid, class_by_hid, record)


if __name__ == "__main__":
    main()
