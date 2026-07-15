from docent_investigation.anchor import wilson_ci
from docent_investigation.fidelity import cohen_kappa, label_fidelity
from docent_investigation.validation import (
    DEFAULT_THRESHOLD,
    compute_validation,
    consensus_labels,
    evaluate_judge_decision,
    presentation_order,
)

D, N = "declared_success", "not_declared"


def test_confusion_matrix_counts_and_estimands():
    judge = {"a": D, "b": D, "c": N, "d": N}
    human = {"a": D, "b": N, "c": D, "d": N}
    v = compute_validation(judge, human)
    assert (v.tp, v.fp, v.fn, v.tn) == (1, 1, 1, 1)
    assert v.n_labeled == 4
    assert v.precision == 0.5 and v.recall == 0.5 and v.f1 == 0.5 and v.agreement == 0.5


def test_positive_label_orientation_flips_the_matrix():
    judge = {"a": D, "b": D, "c": D, "d": N}
    human = {"a": D, "b": N, "c": D, "d": N}
    as_declared = compute_validation(judge, human, positive_label=D)
    assert (as_declared.tp, as_declared.fp, as_declared.fn, as_declared.tn) == (2, 1, 0, 1)
    as_not_declared = compute_validation(judge, human, positive_label=N)
    assert (as_not_declared.tp, as_not_declared.fp, as_not_declared.fn, as_not_declared.tn) == (1, 0, 1, 2)


def test_estimand_cis_are_wilson_intervals():
    judge = {"a": D, "b": D, "c": N, "d": N}
    human = {"a": D, "b": N, "c": D, "d": N}
    v = compute_validation(judge, human)
    assert v.precision_ci == wilson_ci(v.tp, v.tp + v.fp)
    assert v.recall_ci == wilson_ci(v.tp, v.tp + v.fn)


def _judge_positives_with_confirmations(n_positive: int, n_confirmed: int):
    ids = [f"p{i}" for i in range(n_positive)]
    judge = {i: D for i in ids}
    human = {i: (D if k < n_confirmed else N) for k, i in enumerate(ids)}
    return judge, human


def test_decision_supported_at_18_of_19():
    v = compute_validation(*_judge_positives_with_confirmations(19, 18))
    decision = evaluate_judge_decision(v)
    assert decision.verdict == "SUPPORTED"
    assert decision.ci[0] >= DEFAULT_THRESHOLD


def test_decision_not_supported_at_17_of_19():
    v = compute_validation(*_judge_positives_with_confirmations(19, 17))
    decision = evaluate_judge_decision(v)
    assert decision.verdict == "NOT_SUPPORTED"
    assert decision.ci[0] < DEFAULT_THRESHOLD


def test_decision_undefined_without_judge_positives():
    v = compute_validation({"a": N, "b": N}, {"a": D, "b": N})
    assert evaluate_judge_decision(v).verdict == "UNDEFINED"


def test_kappa_and_agreement_match_fidelity_on_same_pairs():
    judge = {"a": D, "b": D, "c": N, "d": N}
    human = {"a": D, "b": N, "c": D, "d": N}
    v = compute_validation(judge, human)
    rows = [{"instance_id": i, "rubric_label": judge[i], "explanation": ""} for i in sorted(judge)]
    fid = label_fidelity(rows, human_labels=human)
    assert v.agreement == fid.human_agreement
    assert v.cohen_kappa == fid.cohen_kappa
    assert v.cohen_kappa == cohen_kappa([(judge[i], human[i]) for i in sorted(judge)])


def test_presentation_order_is_a_deterministic_seeded_permutation():
    ids = [f"inst-{i}" for i in range(20)]
    first = presentation_order(ids, seed=20260715)
    assert presentation_order(list(reversed(ids)), seed=20260715) == first  # input order irrelevant
    assert sorted(first) == sorted(ids)
    assert presentation_order(ids, seed=1) != first


def test_consensus_single_rater_passes_through():
    entries = [{"instance_id": "a", "label": D, "rater_id": "ed"},
               {"instance_id": "b", "label": N, "rater_id": "ed"}]
    consensus, disagreements = consensus_labels(entries)
    assert consensus == {"a": D, "b": N}
    assert disagreements == []


def test_consensus_two_raters_unanimous_and_disagreeing():
    entries = [
        {"instance_id": "a", "label": D, "rater_id": "r1"},
        {"instance_id": "a", "label": D, "rater_id": "r2"},
        {"instance_id": "b", "label": D, "rater_id": "r1"},
        {"instance_id": "b", "label": N, "rater_id": "r2"},
    ]
    consensus, disagreements = consensus_labels(entries)
    assert consensus == {"a": D}
    assert disagreements == ["b"]
