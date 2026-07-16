"""Layer tests for the step-4 instrument and the pre-registered paired analysis (offline, pure)."""

from __future__ import annotations

import pytest

from docent_investigation.gap3_baseline import BEHAVIOR_CLASSES, STOCK_OUTPUT_SCHEMA
from docent_investigation.gap3_step4 import (
    BASELINE_FLAG_COUNT,
    discordant_counts,
    headline_verdict,
    mcnemar_exact_one_sided,
    paired_rows,
    policy_rubric,
)


def pair(hid, cls, base_rec, pol_rec, base_flag=None, pol_flag=None):
    return {
        "haystack_id": hid,
        "behavior_class": cls,
        "baseline_recovered": base_rec,
        "policy_recovered": pol_rec,
        "baseline_flagged": base_rec if base_flag is None else base_flag,
        "policy_flagged": pol_rec if pol_flag is None else pol_flag,
    }


def row(hid, cls, flagged, recovered):
    return {"haystack_id": hid, "behavior_class": cls, "flagged": flagged, "recovered": recovered}


def test_mcnemar_known_values():
    assert mcnemar_exact_one_sided(0, 0) is None
    assert mcnemar_exact_one_sided(5, 0) == pytest.approx(1 / 32)
    assert mcnemar_exact_one_sided(7, 1) == pytest.approx(9 / 256)
    assert mcnemar_exact_one_sided(4, 0) == pytest.approx(1 / 16)
    assert mcnemar_exact_one_sided(1, 3) == pytest.approx(15 / 16)


def test_policy_rubric_is_stock_schema_and_names_all_classes():
    spec = policy_rubric()
    assert spec.output_schema is STOCK_OUTPUT_SCHEMA  # identical object, not a copy
    for cls in BEHAVIOR_CLASSES:
        assert cls in spec.text
    assert "specific citations" in spec.text


def test_paired_rows_joins_by_haystack_id():
    base = [row("h002", "sandbagging", True, False), row("h001", "fabrication", True, True)]
    policy = [row("h001", "fabrication", True, True), row("h002", "sandbagging", True, True)]
    pairs = paired_rows(base, policy)
    assert [p["haystack_id"] for p in pairs] == ["h001", "h002"]
    assert pairs[1] == pair("h002", "sandbagging", False, True, base_flag=True)


def test_paired_rows_refuses_set_mismatch():
    with pytest.raises(ValueError):
        paired_rows([row("h001", "fabrication", True, True)],
                    [row("h002", "fabrication", True, True)])


def test_discordant_counts_directions():
    pairs = [pair("h001", "fabrication", True, True),
             pair("h002", "sandbagging", False, True),
             pair("h003", "reward_hacking", False, True),
             pair("h004", "sandbagging", True, False)]
    result = discordant_counts(pairs, "baseline_recovered", "policy_recovered")
    assert (result["policy_only"], result["baseline_only"]) == (2, 1)
    assert result["p_one_sided"] == pytest.approx(0.5)


def test_headline_verdict_supported_gate_failed_not_supported():
    significant = {"p_one_sided": mcnemar_exact_one_sided(5, 0)}
    assert headline_verdict(significant, BASELINE_FLAG_COUNT)["verdict"] == "SUPPORTED"
    assert headline_verdict(significant, BASELINE_FLAG_COUNT + 1)["verdict"] == "GATE_FAILED"
    weak = {"p_one_sided": mcnemar_exact_one_sided(4, 0)}
    assert headline_verdict(weak, 0)["verdict"] == "NOT_SUPPORTED"
    assert headline_verdict({"p_one_sided": None}, 0)["verdict"] == "NOT_SUPPORTED"
