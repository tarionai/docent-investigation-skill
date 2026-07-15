"""Judge validation (pure stats): the rubric judge measured against blind human ground truth.

This is the instrument-validation half that the oracle anchor cannot provide: the anchor cross-tabs
judge labels against task OUTCOMES, while this module cross-tabs judge labels against an independent
human's blind reading of the same transcripts. Human labels are the ground truth by convention
(PRE_REGISTRATION_JUDGE_VALIDATION.md); the pre-registered verdict keys on ONE primary estimand —
judge precision — with recall, agreement, and Cohen's kappa reported descriptively. No I/O.
"""

from __future__ import annotations

import random
from dataclasses import asdict, dataclass

from .anchor import Decision, wilson_ci
from .fidelity import cohen_kappa
from .rubric import LABEL_DECLARED

PRIMARY_ESTIMAND = "judge_precision"
DEFAULT_THRESHOLD = 0.70  # pre-registered; with 19 judge-positives, reachable only at >=18/19 confirmed

DISCLOSURE = (
    "Human labels are the ground-truth convention, not an oracle: one rater is a weak bound, two "
    "raters + adjudication is the standard, and any rater contamination is disclosed in the "
    "pre-registration. The verdict keys on judge precision only; recall, agreement, and kappa are "
    "descriptive."
)


@dataclass(frozen=True)
class JudgeValidation:
    n_labeled: int
    tp: int
    fp: int
    fn: int
    tn: int
    precision: float | None
    precision_ci: tuple[float, float] | None
    recall: float | None
    recall_ci: tuple[float, float] | None
    f1: float | None
    agreement: float | None
    cohen_kappa: float | None
    positive_label: str
    disclosure: str

    def as_dict(self) -> dict:
        return asdict(self)


def _safe_div(num: int, den: int) -> float | None:
    return num / den if den else None


def compute_validation(
    judge_labels: dict[str, str],
    human_labels: dict[str, str],
    positive_label: str = LABEL_DECLARED,
) -> JudgeValidation:
    """Confusion matrix and estimands over the id intersection; the human label is ground truth."""
    ids = sorted(set(judge_labels) & set(human_labels))
    pairs = [(judge_labels[i], human_labels[i]) for i in ids]
    tp = sum(j == positive_label and h == positive_label for j, h in pairs)
    fp = sum(j == positive_label and h != positive_label for j, h in pairs)
    fn = sum(j != positive_label and h == positive_label for j, h in pairs)
    tn = sum(j != positive_label and h != positive_label for j, h in pairs)
    return JudgeValidation(
        n_labeled=len(ids),
        tp=tp,
        fp=fp,
        fn=fn,
        tn=tn,
        precision=_safe_div(tp, tp + fp),
        precision_ci=wilson_ci(tp, tp + fp),
        recall=_safe_div(tp, tp + fn),
        recall_ci=wilson_ci(tp, tp + fn),
        f1=_safe_div(2 * tp, 2 * tp + fp + fn),
        agreement=_safe_div(tp + tn, len(ids)),
        cohen_kappa=cohen_kappa(pairs),
        positive_label=positive_label,
        disclosure=DISCLOSURE,
    )


def evaluate_judge_decision(v: JudgeValidation, threshold: float = DEFAULT_THRESHOLD) -> Decision:
    """Pre-registered verdict on ONE primary estimand: judge precision.

    SUPPORTED iff precision's Wilson 95% lower bound is at or above ``threshold``. With no
    judge-positive labeled runs the estimand is undefined (UNDEFINED). Recall and kappa are
    deliberately NOT part of this verdict.
    """
    if v.precision is None or v.precision_ci is None:
        return Decision("UNDEFINED", PRIMARY_ESTIMAND, threshold, None, None,
                        "no judge-positive labeled runs: precision is undefined")
    if v.precision_ci[0] >= threshold:
        return Decision("SUPPORTED", PRIMARY_ESTIMAND, threshold, v.precision, v.precision_ci,
                        f"95% CI lower bound {v.precision_ci[0]:.3f} >= {threshold:.2f}")
    return Decision("NOT_SUPPORTED", PRIMARY_ESTIMAND, threshold, v.precision, v.precision_ci,
                    f"95% CI lower bound {v.precision_ci[0]:.3f} < {threshold:.2f} "
                    f"(estimate {v.precision:.3f} at n={v.tp + v.fp})")


def presentation_order(instance_ids: list[str], seed: int) -> list[str]:
    """Deterministic shuffled labeling order: same seed, same order, on any machine."""
    ordered = sorted(instance_ids)
    random.Random(seed).shuffle(ordered)
    return ordered


def consensus_labels(entries: list[dict]) -> tuple[dict[str, str], list[str]]:
    """Collapse per-rater label entries (keys: instance_id, label) into consensus ground truth.

    Unanimous instances map to their label; instances where raters disagree are returned separately
    for adjudication and are excluded from the consensus until adjudicated.
    """
    by_instance: dict[str, set[str]] = {}
    for e in entries:
        by_instance.setdefault(e["instance_id"], set()).add(e["label"])
    consensus = {i: next(iter(labels)) for i, labels in by_instance.items() if len(labels) == 1}
    disagreements = sorted(i for i in by_instance if i not in consensus)
    return consensus, disagreements
