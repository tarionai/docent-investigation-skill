"""Blind labeling CLI: collect human ground-truth labels for the judge-validation study.

Sole writer of reports/human_labels.json; this script reads NO judge output, so the rater cannot be
influenced by it (enforced by tests/test_rater_blindness.py). Each pinned run is shown exactly as
the blind judge saw it (transform.record_to_blind_text), in a seeded shuffled order, and the store
is rewritten after every label so a session can stop and resume at any point. A second rater runs
the same command with a different --rater. Protocol: PRE_REGISTRATION_JUDGE_VALIDATION.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from docent_investigation.rubric import LABEL_DECLARED, LABEL_NOT_DECLARED
from docent_investigation.transform import record_to_blind_text
from docent_investigation.validation import presentation_order

PROTOCOL = "PRE_REGISTRATION_JUDGE_VALIDATION.md"
PROMPT = f"[d] {LABEL_DECLARED}   [n] {LABEL_NOT_DECLARED}   [s] skip   [q] quit > "
KEY_TO_LABEL = {"d": LABEL_DECLARED, "n": LABEL_NOT_DECLARED}


def _load_manifest(path: Path) -> dict[str, dict]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return {entry["instance_id"]: entry for entry in manifest["records"]}


def _load_store(path: Path, seed: int) -> dict:
    if path.exists():
        store = json.loads(path.read_text(encoding="utf-8"))
        if store.get("seed") != seed:
            raise SystemExit(f"{path} was collected under seed {store.get('seed')}, not {seed}")
        return store
    return {"schema_version": 1, "protocol": PROTOCOL, "seed": seed, "labels": []}


def _read_record(records_dir: Path, entry: dict) -> dict:
    raw = (records_dir / entry["file"]).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != entry["sha256"]:
        raise SystemExit(f"sha256 mismatch for {entry['file']}: not the pinned record — aborting")
    return json.loads(raw.decode("utf-8"))


def _ask_label() -> str | None:
    """Return a label, 'skip', or None to quit."""
    while True:
        key = input(PROMPT).strip().lower()
        if key in KEY_TO_LABEL:
            return KEY_TO_LABEL[key]
        if key == "s":
            return "skip"
        if key == "q":
            return None


def main() -> None:
    # Transcripts contain characters outside the Windows-console default codepage
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default="data")
    parser.add_argument("--manifest", default="reports/sample_manifest.json")
    parser.add_argument("--out", default="reports/human_labels.json")
    parser.add_argument("--rater", required=True, help="rater id recorded with every label")
    parser.add_argument("--seed", type=int, default=20260715, help="pre-registered shuffle seed")
    args = parser.parse_args()

    entries = _load_manifest(Path(args.manifest))
    out_path = Path(args.out)
    store = _load_store(out_path, args.seed)
    done = {label["instance_id"] for label in store["labels"] if label["rater_id"] == args.rater}
    order = presentation_order(list(entries), args.seed)
    pending = [i for i in order if i not in done]
    print(f"rater={args.rater}  labeled={len(done)}  pending={len(pending)}  seed={args.seed}")

    for instance_id in pending:
        record = _read_record(Path(args.data) / "records", entries[instance_id])
        print("\n" + "=" * 78 + f"\nrun {order.index(instance_id) + 1}/{len(order)}\n" + "=" * 78)
        print(record_to_blind_text(record))
        label = _ask_label()
        if label is None:
            break
        if label == "skip":
            continue
        store["labels"].append({
            "instance_id": instance_id,
            "label": label,
            "rater_id": args.rater,
            "labeled_at_utc": datetime.now(timezone.utc).isoformat(),
            "order_index": order.index(instance_id),
        })
        out_path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"saved -> {out_path} ({len(store['labels'])} labels total)")


if __name__ == "__main__":
    main()
