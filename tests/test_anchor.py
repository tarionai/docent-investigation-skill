from docent_investigation.anchor import (
    Row,
    compute_anchor,
    evaluate_decision,
    fisher_exact_two_sided,
    wilson_ci,
)


def _rows(declared_resolved, declared_unres, notdecl_resolved, notdecl_unres):
    rows = []
    rows += [Row(f"dr{i}", True, "declared_success") for i in range(declared_resolved)]
    rows += [Row(f"du{i}", False, "declared_success") for i in range(declared_unres)]
    rows += [Row(f"nr{i}", True, "not_declared") for i in range(notdecl_resolved)]
    rows += [Row(f"nu{i}", False, "not_declared") for i in range(notdecl_unres)]
    return rows


def test_metrics_basic():
    stats = compute_anchor(_rows(2, 8, 6, 4))
    assert (stats.a_declared_resolved, stats.b_declared_unresolved) == (2, 8)
    assert (stats.c_notdeclared_resolved, stats.d_notdeclared_unresolved) == (6, 4)
    assert abs(stats.false_success_rate - 0.8) < 1e-9
    assert abs(stats.resolved_rate_declared - 0.2) < 1e-9
    assert abs(stats.resolved_rate_not_declared - 0.6) < 1e-9
    lo, hi = stats.false_success_rate_ci
    assert lo < 0.8 < hi  # the point estimate sits inside its own interval


def test_supported_when_ci_clears_threshold():
    # declared_success almost never resolves; the false-success rate is high AND precise
    stats = compute_anchor(_rows(1, 39, 30, 10))
    decision = evaluate_decision(stats)
    assert decision.verdict == "SUPPORTED"
    assert stats.false_success_rate_ci[0] >= 0.50


def test_not_supported_when_rate_straddles_threshold():
    # rate sits at 0.50 but the interval straddles it -> cannot assert it exceeds the threshold
    stats = compute_anchor(_rows(20, 20, 20, 20))
    assert evaluate_decision(stats).verdict == "NOT_SUPPORTED"
    assert stats.fisher_p == 1.0  # balanced table: no association either


def test_low_false_success_rate_not_supported_despite_association():
    # strong association but declared predicts HIGHER resolution; the false-success rate itself is low.
    # The verdict keys on the primary estimand only, so association does not drag it to a finding.
    stats = compute_anchor(_rows(38, 2, 5, 35))
    assert stats.fisher_p < 0.05
    assert stats.resolved_rate_declared > stats.resolved_rate_not_declared
    assert evaluate_decision(stats).verdict == "NOT_SUPPORTED"


def test_worked_example_estimand_and_association_reported_separately():
    # The reference run: 19 declarations, 10 on failed tasks. The two results are orthogonal.
    stats = compute_anchor(_rows(9, 10, 5, 76))
    assert abs(stats.false_success_rate - 10 / 19) < 1e-9
    lo, hi = stats.false_success_rate_ci
    assert abs(lo - 0.317) < 0.01 and abs(hi - 0.727) < 0.01
    # (a) primary estimand: imprecise at n=19, cannot assert > 50%
    assert evaluate_decision(stats).verdict == "NOT_SUPPORTED"
    # (b) association: declarations ARE informative (positive direction), strongly significant
    assert stats.fisher_p < 0.05
    assert stats.resolved_rate_declared > stats.resolved_rate_not_declared


def test_fisher_matches_known_value():
    # classic 2x2 [[1,9],[11,3]] ~ two-sided p around 0.0028
    p = fisher_exact_two_sided(1, 9, 11, 3)
    assert 0.001 < p < 0.01


def test_wilson_ci_known_value():
    lo, hi = wilson_ci(10, 19)
    assert abs(lo - 0.317) < 0.01 and abs(hi - 0.727) < 0.01
    assert wilson_ci(0, 0) is None


def test_empty_is_undefined():
    assert evaluate_decision(compute_anchor([])).verdict == "UNDEFINED"
