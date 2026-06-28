from docent_investigation.anchor import Row, compute_anchor, fisher_exact_two_sided


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


def test_strong_false_success_finding():
    # declared_success almost never resolves; not_declared resolves often; large, separable sample
    stats = compute_anchor(_rows(1, 39, 30, 10))
    assert stats.fisher_p < 0.05
    assert stats.decision == "FALSE_SUCCESS_FINDING"


def test_null_when_no_separation():
    # declared and not_declared resolve at the same rate -> NULL
    stats = compute_anchor(_rows(20, 20, 20, 20))
    assert stats.decision == "NULL"


def test_inconclusive_when_declared_predicts_higher_resolution():
    # significant but the WRONG direction for a false-success finding (declared resolves MORE)
    stats = compute_anchor(_rows(38, 2, 5, 35))
    assert stats.fisher_p < 0.05
    assert stats.decision == "INCONCLUSIVE"


def test_fisher_matches_known_value():
    # classic 2x2 [[1,9],[11,3]] ~ two-sided p around 0.0028
    p = fisher_exact_two_sided(1, 9, 11, 3)
    assert 0.001 < p < 0.01


def test_empty_is_inconclusive():
    assert compute_anchor([]).decision == "INCONCLUSIVE"
