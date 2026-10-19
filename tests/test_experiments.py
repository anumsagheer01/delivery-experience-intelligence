"""Unit tests: experiment assignment, power, and analysis."""
import math

import numpy as np
import pytest
from scipy import stats

from src.experiments import analysis, assignment, design, power


# assignment -----------------------------------------------------------

def test_assignment_is_deterministic():
    a1 = assignment.assign("cust_123")
    a2 = assignment.assign("cust_123")
    assert a1 == a2
    assert a1 in design.ARMS


def test_assignment_split_is_roughly_even():
    arms = [assignment.assign(f"cust_{i}") for i in range(4000)]
    frac = sum(a == "treatment" for a in arms) / len(arms)
    assert 0.45 < frac < 0.55


def test_assignment_salt_changes_allocation():
    same = sum(
        assignment.assign(f"cust_{i}", salt="v1")
        == assignment.assign(f"cust_{i}", salt="v2")
        for i in range(2000)
    ) / 2000
    assert 0.4 < same < 0.6  # independent draws, not identical


def test_assignment_rejects_bad_allocation():
    with pytest.raises(ValueError):
        assignment.assign("cust_1", allocation=(0.5, 0.6))


def test_draft_never_sends():
    msg = assignment.draft_outreach_message("Ana", "ord_1", "late")
    assert msg["sent"] is False
    assert design.SEND_MESSAGES is False


# power ----------------------------------------------------------------

def test_sample_size_known_value():
    # std=1, mde=0.5, alpha=0.05, power=0.8 -> 2*((1.96+0.84)/0.5)^2 = 62.72
    assert power.sample_size_two_sample(1.0, 0.5) == pytest.approx(62.72,
                                                                  rel=0.01)


def test_design_effect_no_clustering():
    assert power.design_effect(1.0, 0.45) == pytest.approx(1.0)


def test_obf_boundaries_shape():
    bounds, info, spent = power.obf_boundaries(4, 0.05)
    assert len(bounds) == 4
    assert all(b > 0 for b in bounds)
    # OBF bounds decrease: early looks demand stronger evidence
    assert bounds[0] > bounds[1] > bounds[2] > bounds[3]
    # final bound sits just above the fixed-design 1.96, because a little
    # alpha was spent at the early looks
    assert 1.96 < bounds[3] < 2.10
    # all alpha is spent by the final look, none overspent
    assert spent[-1] == pytest.approx(0.05, rel=0.01)
    assert all(s <= 0.05 + 1e-9 for s in spent)
    assert info == [0.25, 0.5, 0.75, 1.0]


# analysis ---------------------------------------------------------------

def test_welch_ttest_matches_scipy():
    rng = np.random.default_rng(0)
    t = rng.normal(0.3, 1.0, 200)
    c = rng.normal(0.0, 1.0, 200)
    r = analysis.welch_ttest(t, c)
    ref = stats.ttest_ind(t, c, equal_var=False)
    assert r["t_stat"] == pytest.approx(ref.statistic)
    assert r["p_value"] == pytest.approx(ref.pvalue)
    assert r["ci_low"] < r["diff"] < r["ci_high"]
    assert r["diff"] == pytest.approx(t.mean() - c.mean())


def test_proportion_test_direction():
    r = analysis.proportion_test(60, 500, 40, 500)
    assert r["diff"] == pytest.approx(0.04)
    assert r["ci_low"] < r["diff"] < r["ci_high"]


def test_cuped_gate_accepts_strong_covariate():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, 2000)
    y = 2 * x + rng.normal(0, 1, 2000)
    use_it, theta, reduction = analysis.cuped_gate(y, x)
    assert use_it is True
    assert theta == pytest.approx(2.0, rel=0.1)
    assert reduction > 0.5


def test_cuped_gate_rejects_noise_covariate():
    rng = np.random.default_rng(2)
    y = rng.normal(0, 1, 2000)
    x = rng.normal(0, 1, 2000)
    use_it, _, reduction = analysis.cuped_gate(y, x)
    assert use_it is False
    assert reduction < design.CUPED_MIN_VARIANCE_REDUCTION


def test_sequential_decision_rejects_and_stops():
    bounds = [3.92, 2.77, 2.27, 1.95]
    dec = analysis.sequential_decision([1.0, 2.9, 0.5, 0.5], bounds)
    assert [d["decision"] for d in dec] == ["continue", "reject"]
    assert dec[-1]["look"] == 2  # stops at first crossing


def test_sequential_decision_continues():
    bounds = [3.92, 2.77, 2.27, 1.95]
    dec = analysis.sequential_decision([1.0, 1.5, 2.0, 1.8], bounds)
    assert all(d["decision"] == "continue" for d in dec)
    assert len(dec) == 4


def test_no_em_dashes_in_module_docstrings():
    import src.experiments as m
    import pathlib
    for f in pathlib.Path(m.__path__[0]).glob("*.py"):
        assert "\u2014" not in f.read_text(), f"em dash in {f}"
        assert "\u2013" not in f.read_text(), f"en dash in {f}"
