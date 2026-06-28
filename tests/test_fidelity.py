from docent_investigation.fidelity import label_fidelity


def _row(instance_id, rubric_label, explanation=""):
    return {"instance_id": instance_id, "rubric_label": rubric_label, "explanation": explanation}


def test_self_consistency_counts_completion_language_in_declared_only():
    rows = [
        _row("a", "declared_success", "The agent says: the issue is now fixed and all tests pass."),
        _row("b", "declared_success", "Let me search more broadly for usage; then the transcript stops."),
        _row("c", "not_declared", "fixed completed done"),  # ignored: not a declared row
    ]
    fid = label_fidelity(rows)
    assert fid.n_declared == 2
    assert abs(fid.judge_self_consistency - 0.5) < 1e-9


def test_no_declared_rows_yields_none():
    fid = label_fidelity([_row("a", "not_declared", "nothing here")])
    assert fid.n_declared == 0
    assert fid.judge_self_consistency is None


def test_human_agreement_and_kappa_perfect():
    rows = [_row("a", "declared_success"), _row("b", "not_declared")]
    human = {"a": "declared_success", "b": "not_declared"}
    fid = label_fidelity(rows, human_labels=human)
    assert fid.n_human_labeled == 2
    assert fid.human_agreement == 1.0
    assert abs(fid.cohen_kappa - 1.0) < 1e-9


def test_human_agreement_partial():
    rows = [_row(x, "declared_success") for x in ("a", "b", "c", "d")]
    human = {"a": "declared_success", "b": "declared_success", "c": "not_declared", "d": "not_declared"}
    fid = label_fidelity(rows, human_labels=human)
    assert fid.n_human_labeled == 4
    assert fid.human_agreement == 0.5  # rubric all-declared, human split


def test_disclosure_is_always_present():
    fid = label_fidelity([_row("a", "declared_success", "fixed")])
    assert "NOT validated by the oracle" in fid.disclosure
