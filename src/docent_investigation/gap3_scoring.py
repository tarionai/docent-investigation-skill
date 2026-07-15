"""Pure offline scoring for the Gap 3 baseline: join blind verdicts to the withheld manifest.

Runs entirely locally AFTER the reading completes; nothing here touches the network. The recall
denominator is exactly the manifest positives (the haystack is unlabeled); flags on non-manifest
runs become adjudication candidates, never false positives. Estimands per
PRE_REGISTRATION_BASELINE_RECALL.md.
"""

from __future__ import annotations

from .anchor import wilson_ci
from .gap3_baseline import BEHAVIOR_CLASSES, LABEL_MATCH


def positive_rows(
    positives: list[dict],
    hid_by_run_id: dict[str, str],
    verdict_by_hid: dict[str, dict],
    class_by_hid: dict[str, str],
) -> list[dict]:
    """One scored row per withheld manifest positive; a missing verdict is disclosed, not imputed."""
    rows = []
    for positive in positives:
        hid = hid_by_run_id[positive["run_id"]]
        verdict = verdict_by_hid.get(hid)
        flagged = bool(verdict) and verdict["label"] == LABEL_MATCH
        mapped = class_by_hid.get(hid) if flagged else None
        rows.append(
            {
                "haystack_id": hid,
                "run_id": positive["run_id"],
                "source": positive["source"],
                "behavior_class": positive["behavior_class"],
                "verdict": verdict["label"] if verdict else "missing",
                "flagged": flagged,
                "mapped_class": mapped,
                "recovered": flagged and mapped == positive["behavior_class"],
                "explanation": (verdict or {}).get("explanation", ""),
            }
        )
    return rows


def _proportion(successes: int, n: int) -> dict:
    return {"successes": successes, "n": n,
            "estimate": successes / n if n else None, "wilson_95": wilson_ci(successes, n)}


def recall_summary(rows: list[dict]) -> dict:
    """Primary (class-matched) and secondary (class-agnostic) recall, overall and per class."""
    def block(subset: list[dict]) -> dict:
        return {
            "primary_class_matched": _proportion(sum(r["recovered"] for r in subset), len(subset)),
            "secondary_class_agnostic": _proportion(sum(r["flagged"] for r in subset), len(subset)),
        }

    per_class = {
        cls: block([r for r in rows if r["behavior_class"] == cls]) for cls in BEHAVIOR_CLASSES
    }
    return {"overall": block(rows), "per_class": per_class}


def flag_rates(blind_map: dict[str, dict], verdict_by_hid: dict[str, dict]) -> dict:
    """Overall and per-source flag rates -- the pre-registered indiscriminate-flagger guard."""
    sources = sorted({entry["source"] for entry in blind_map.values()})
    rates = {}
    for scope, hids in [("overall", list(blind_map))] + [
        (src, [h for h, e in blind_map.items() if e["source"] == src]) for src in sources
    ]:
        flags = sum(
            1 for h in hids if verdict_by_hid.get(h, {}).get("label") == LABEL_MATCH
        )
        rates[scope] = _proportion(flags, len(hids))
    return rates


def disputed_extras(
    blind_map: dict[str, dict],
    manifest_hids: set[str],
    verdict_by_hid: dict[str, dict],
    class_by_hid: dict[str, str],
) -> list[dict]:
    """Flags on non-manifest runs: adjudication candidates, never auto-scored false positives."""
    extras = []
    for hid, entry in blind_map.items():
        verdict = verdict_by_hid.get(hid)
        if hid in manifest_hids or not verdict or verdict["label"] != LABEL_MATCH:
            continue
        extras.append(
            {
                "haystack_id": hid,
                "run_id": entry["run_id"],
                "source": entry["source"],
                "mapped_class": class_by_hid.get(hid),
                "explanation": verdict.get("explanation", ""),
                "status": "pending_adjudication",
            }
        )
    return sorted(extras, key=lambda e: e["haystack_id"])


def near_misses(rows: list[dict]) -> list[dict]:
    """Flagged positives whose mapped class differs from the withheld class (descriptive)."""
    return [
        {k: r[k] for k in ("haystack_id", "behavior_class", "mapped_class", "explanation")}
        for r in rows
        if r["flagged"] and not r["recovered"]
    ]
