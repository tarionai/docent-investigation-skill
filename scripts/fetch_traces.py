"""Fetch OpenHands SWE-bench-Verified traces + resolution oracle from a public HF dataset.

Source: https://huggingface.co/datasets/pankajmathur/nemotron-nano-swebench-verified-traj
- oracle  : openhands/openhands.eval_output.swebench.json  (resolved_ids / unresolved_ids / empty_patch_ids)
- records : openhands/output.jsonl                          (one OpenHands record per line, streamed)

Writes <out>/oracle_summary.json and <out>/records/<instance_id>.json. Streams and stops early so it
does not download the full 155MB unless --n is large. Read-only public data; no auth.
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

DATASET = "pankajmathur/nemotron-nano-swebench-verified-traj"
BASE = f"https://huggingface.co/datasets/{DATASET}/resolve/main/openhands"
_HEADERS = {"User-Agent": "docent-investigation"}


def _open(url: str, timeout: int = 300):
    return urllib.request.urlopen(urllib.request.Request(url, headers=_HEADERS), timeout=timeout)


def fetch_oracle(out_dir: Path) -> Path:
    out = out_dir / "oracle_summary.json"
    with _open(f"{BASE}/openhands.eval_output.swebench.json", timeout=120) as resp:
        out.write_bytes(resp.read())
    return out


def fetch_records(out_dir: Path, n: int) -> list[str]:
    rec_dir = out_dir / "records"
    rec_dir.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    with _open(f"{BASE}/output.jsonl") as resp:
        buf = b""
        while len(written) < n:
            chunk = resp.read(65536)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf and len(written) < n:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                instance_id = json.loads(line)["instance_id"]
                (rec_dir / f"{instance_id}.json").write_bytes(line)
                written.append(instance_id)
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data", help="output directory (gitignored)")
    parser.add_argument("--n", type=int, default=60, help="number of records to fetch")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    oracle_path = fetch_oracle(out_dir)
    records = fetch_records(out_dir, args.n)
    print(f"oracle  -> {oracle_path}")
    print(f"records -> {len(records)} written to {out_dir / 'records'}")


if __name__ == "__main__":
    main()
