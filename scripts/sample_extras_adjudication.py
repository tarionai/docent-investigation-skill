"""Deterministic stratified sample of the baseline's 122 extra flags for blind adjudication.

Census of every MALT extra plus a seeded draw of --per-stratum ids from each remaining source
stratum (seed frozen in PRE_REGISTRATION_EXTRAS_ADJUDICATION.md). The sample document pins the
queue file's sha256 and each sampled archive's sha256 so the adjudication CLI can refuse unpinned
inputs; judge output never enters the document, so opening it does not unblind the rater. The
frozen sample is never overwritten: the only permitted mutation is the pre-registered escape hatch
(--extend SOURCE), which moves the next ids of the frozen extension order into the sample.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from docent_investigation.gap3_extras import (
    PER_STRATUM,
    SAMPLE_SEED,
    build_sample_document,
    extend_sample_document,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _archive_info(corpus: Path, queue: list[dict]) -> dict[str, dict]:
    info = {}
    for entry in queue:
        rel = f"{entry['source']}/runs/{entry['run_id']}.json"
        info[entry["haystack_id"]] = {"archive": rel, "archive_sha256": _sha256(corpus / rel)}
    return info


def _print_summary(doc: dict, out: Path) -> None:
    counts = {}
    for entry in doc["sampled"]:
        counts[entry["source"]] = counts.get(entry["source"], 0) + 1
    print(f"sample document: {out}  sha256={_sha256(out)}")
    print(f"queue sha256 pinned: {doc['queue_sha256']}")
    print(f"per-stratum sampled counts: {counts}")
    flat = sorted(entry["haystack_id"] for entry in doc["sampled"])
    print(f"sampled haystack_ids (flat, sorted, {len(flat)} total -- no stratum attribution):")
    print(", ".join(flat))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default="data/gap3_corpus_v0")
    parser.add_argument("--queue", default="data/gap3_corpus_v0/adjudication_queue_baseline.json")
    parser.add_argument("--out", default="data/gap3_corpus_v0/extras_adjudication_sample.json")
    parser.add_argument("--seed", type=int, default=SAMPLE_SEED)
    parser.add_argument("--per-stratum", type=int, default=PER_STRATUM)
    parser.add_argument("--extend", metavar="SOURCE", default=None,
                        help="pre-registered escape hatch: move the next ids of SOURCE's frozen "
                             "extension order into the sample")
    args = parser.parse_args()

    corpus, out_path = Path(args.corpus), Path(args.out)
    queue_path = Path(args.queue)
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    info = _archive_info(corpus, queue)
    now = datetime.now(timezone.utc).isoformat()
    if args.extend:
        doc = json.loads(out_path.read_text(encoding="utf-8"))
        if doc["queue_sha256"] != _sha256(queue_path):
            sys.exit("queue sha256 mismatch: not the pinned queue -- aborting")
        doc = extend_sample_document(doc, args.extend, queue, info, now)
    else:
        if out_path.exists():
            sys.exit(f"{out_path} already exists -- the sample is frozen; use --extend SOURCE")
        doc = build_sample_document(queue, args.seed, args.per_stratum, _sha256(queue_path),
                                    info, now)
    out_path.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    _print_summary(doc, out_path)


if __name__ == "__main__":
    main()
