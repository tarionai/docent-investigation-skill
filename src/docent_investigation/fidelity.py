"""Label-fidelity check (pure): how trustworthy are the rubric's labels themselves?

The oracle anchor validates OUTCOMES (did the patch resolve), not whether the rubric labeled the
transcript correctly. This module reports two signals, and they are NOT interchangeable:

- ``judge_self_consistency``: among ``declared_success`` rows, the fraction whose cited explanation
  contains completion language. This is a SELF-CONSISTENCY sanity check on the judge's own output --
  it does NOT measure fidelity to ground truth (a judge that misreads the transcript can still cite
  completion language). Always available; weak by construction.
- ``human_agreement`` / ``cohen_kappa``: agreement between the rubric label and an INDEPENDENT human
  label, over whatever subset a human labeled. This is the real fidelity measure. ``None`` until a
  human does the labeling -- one rater is a weak bound; two raters + adjudication is the standard.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from .rubric import LABEL_DECLARED

COMPLETION_TERMS = (
    "fix", "fixed", "resolve", "resolved", "complete", "completed", "done",
    "pass", "passes", "passed", "solved", "success", "working",
)

DISCLOSURE = (
    "Label fidelity is NOT validated by the oracle. judge_self_consistency is a self-consistency "
    "sanity check on the judge's own citations, not evidence of correct labeling. To validate "
    "fidelity, blind-label a sample by hand and pass it as human_labels: one rater is a weak bound, "
    "two raters + adjudication is the standard."
)

_TERM_RE = re.compile(r"\b(" + "|".join(COMPLETION_TERMS) + r")\b", re.IGNORECASE)


def _has_completion_language(text: str) -> bool:
    return bool(_TERM_RE.search(text or ""))


def cohen_kappa(pairs: list[tuple[str, str]]) -> float | None:
    """Cohen's kappa for two raters over paired categorical labels."""
    n = len(pairs)
    if n == 0:
        return None
    p_observed = sum(a == b for a, b in pairs) / n
    labels = {x for pair in pairs for x in pair}
    p_expected = sum(
        (sum(a == label for a, _ in pairs) / n) * (sum(b == label for _, b in pairs) / n)
        for label in labels
    )
    return (p_observed - p_expected) / (1 - p_expected) if p_expected != 1 else 1.0


@dataclass(frozen=True)
class LabelFidelity:
    n_declared: int
    judge_self_consistency: float | None
    n_human_labeled: int
    human_agreement: float | None
    cohen_kappa: float | None
    disclosure: str

    def as_dict(self) -> dict:
        return asdict(self)


def label_fidelity(rows: list[dict], human_labels: dict[str, str] | None = None) -> LabelFidelity:
    """Report label-fidelity signals from joined verdict rows (keys: rubric_label, explanation,
    instance_id). ``human_labels`` maps instance_id -> a human's blind label; when supplied, agreement
    and kappa are computed over the overlap. See module docstring for what each signal does and does
    not establish.
    """
    declared = [r for r in rows if r.get("rubric_label") == LABEL_DECLARED]
    self_consistency = (
        sum(_has_completion_language(r.get("explanation", "")) for r in declared) / len(declared)
        if declared else None
    )
    agreement = kappa = None
    pairs = (
        [(r["rubric_label"], human_labels[r["instance_id"]]) for r in rows
         if r.get("instance_id") in human_labels]
        if human_labels else []
    )
    if pairs:
        agreement = sum(a == b for a, b in pairs) / len(pairs)
        kappa = cohen_kappa(pairs)
    return LabelFidelity(
        n_declared=len(declared),
        judge_self_consistency=self_consistency,
        n_human_labeled=len(pairs),
        human_agreement=agreement,
        cohen_kappa=kappa,
        disclosure=DISCLOSURE,
    )
