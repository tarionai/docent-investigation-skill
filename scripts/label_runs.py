"""Blind labeling CLI: collect human ground-truth labels for the judge-validation study.

Sole writer of reports/human_labels.json; this script reads NO judge output, so the rater cannot be
influenced by it (enforced by tests/test_rater_blindness.py). Each pinned run is rendered exactly as
the blind judge saw it (transform.record_to_blind_text), in a seeded shuffled order, and the store
is rewritten after every label so a session can stop and resume at any point. A second rater runs
the same command with a different --rater. Protocol: PRE_REGISTRATION_JUDGE_VALIDATION.md.

Transcripts run thousands of lines, and the rubric question is decided by the agent's FINAL
messages, so the terminal shows only the transcript tail (--tail, 0 = everything); the complete
blind text is written to --view-file (default under gitignored data/) for scrolling when the tail
is ambiguous. The rendered text itself is identical either way.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from docent_investigation.rubric import LABEL_DECLARED, LABEL_NOT_DECLARED, RUBRIC_TEXT
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


def _present_run(record: dict, position: str, view_path: Path, tail: int) -> None:
    """Write the full blind text to view_path and print its tail (or all of it when tail <= 0)."""
    text = record_to_blind_text(record)
    view_path.parent.mkdir(parents=True, exist_ok=True)
    view_path.write_text(text, encoding="utf-8")
    lines = text.splitlines()
    shown = lines if tail <= 0 or tail >= len(lines) else lines[-tail:]
    print("\n" + "=" * 78 + f"\nrun {position}\n" + "=" * 78)
    if len(shown) < len(lines):
        print(f"[... {len(lines) - len(shown)} earlier lines omitted -- full transcript: {view_path}]\n")
    print("\n".join(shown))
    print(f"\n[shown: final {len(shown)} of {len(lines)} lines -- full blind transcript: {view_path}]")


def _review_pending(store: dict, rater: str, review_label: str, order: list[str]) -> list[str]:
    labeled = {e["instance_id"]: e for e in store["labels"] if e["rater_id"] == rater}
    return [i for i in order if i in labeled and labeled[i]["label"] == review_label]


def _record(store: dict, instance_id: str, rater: str, label: str, order_index: int,
            review: bool) -> None:
    """Append a fresh label, or — in review mode — update in place with a full audit trail."""
    now = datetime.now(timezone.utc).isoformat()
    if review:
        entry = next(e for e in store["labels"]
                     if e["instance_id"] == instance_id and e["rater_id"] == rater)
        entry["reviewed_at_utc"] = now
        if label != entry["label"]:
            entry.setdefault("original_label", entry["label"])
            entry["label"] = label
            entry["relabeled_at_utc"] = now
        return
    store["labels"].append({
        "instance_id": instance_id,
        "label": label,
        "rater_id": rater,
        "labeled_at_utc": now,
        "order_index": order_index,
    })


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
    parser.add_argument("--tail", type=int, default=60,
                        help="terminal shows the final N transcript lines (0 = all)")
    parser.add_argument("--view-file", default="data/rater_view.txt",
                        help="full blind transcript of the current run is written here")
    parser.add_argument("--review", metavar="LABEL", default=None,
                        help="re-present this rater's runs currently labeled LABEL (blind), "
                             "reconfirm or correct each; originals kept as audit trail")
    args = parser.parse_args()

    entries = _load_manifest(Path(args.manifest))
    out_path = Path(args.out)
    store = _load_store(out_path, args.seed)
    done = {label["instance_id"] for label in store["labels"] if label["rater_id"] == args.rater}
    order = presentation_order(list(entries), args.seed)
    if args.review:
        pending = _review_pending(store, args.rater, args.review, order)
        print(f"rater={args.rater}  REVIEW of label {args.review!r}: {len(pending)} runs  seed={args.seed}")
    else:
        pending = [i for i in order if i not in done]
        print(f"rater={args.rater}  labeled={len(done)}  pending={len(pending)}  seed={args.seed}")
    print("\nLabeling instruction (the frozen rubric, applied verbatim):\n\n" + RUBRIC_TEXT)

    for instance_id in pending:
        record = _read_record(Path(args.data) / "records", entries[instance_id])
        _present_run(record, f"{order.index(instance_id) + 1}/{len(order)}",
                     Path(args.view_file), args.tail)
        label = _ask_label()
        if label is None:
            break
        if label == "skip":
            continue
        _record(store, instance_id, args.rater, label, order.index(instance_id),
                review=bool(args.review))
        out_path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"saved -> {out_path} ({len(store['labels'])} labels total)")


if __name__ == "__main__":
    main()
