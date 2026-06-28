"""Pin the worked sample: write a tracked manifest of instance_id + sha256 for the fetched records.

`data/` is gitignored, so the records themselves are not committed; this manifest (under `reports/`,
which IS tracked) lets anyone verify they fetched the same N inputs. Deterministic: records are taken
in the same sorted file order as `batch.load_records`, and the hash is over the raw fetched bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SOURCE_DATASET = "pankajmathur/nemotron-nano-swebench-verified-traj"


def write_manifest(data_dir: Path, n: int, out_path: Path) -> dict:
    paths = sorted((data_dir / "records").glob("*.json"))[:n]
    records = []
    for path in paths:
        raw = path.read_bytes()
        instance_id = json.loads(raw).get("instance_id", path.stem)
        records.append(
            {"instance_id": instance_id, "file": path.name, "sha256": hashlib.sha256(raw).hexdigest()}
        )
    manifest = {
        "source_dataset": SOURCE_DATASET,
        "view": "openhands",
        "order": "sorted filename of data/records/*.json, first n (matches batch.load_records)",
        "hash": "sha256 of the raw fetched record bytes",
        "n": len(records),
        "records": records,
    }
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--out", default="reports/sample_manifest.json")
    args = parser.parse_args()
    manifest = write_manifest(Path(args.data_dir), args.n, Path(args.out))
    print(f"wrote {args.out}: {manifest['n']} records from {SOURCE_DATASET}")


if __name__ == "__main__":
    main()
