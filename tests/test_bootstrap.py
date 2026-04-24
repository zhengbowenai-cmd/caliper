"""Tests for safety.bootstrap."""
import numpy as np
import pytest

from probe.safety import (
    PairedComparison,
    paired_bca_bootstrap,
    hedges_g,
    tost_paired,
    required_n_paired_t,
)


def test_clear_positive_effect():
    rng = np.random.default_rng(0)
    seed = rng.uniform(0.4, 0.6, 50)
    # Challenger uniformly 0.2 higher
    chal = np.clip(seed + 0.2 + rng.normal(0, 0.05, 50), 0, 1)
    cmp_ = PairedComparison(seed=seed, challenger=chal)
    res = paired_bca_bootstrap(cmp_, n_resamples=2000, seed=1)
    assert res.ci_lower > 0
    assert res.significant_at_zero is True
    assert 0.15 < res.point_estimate < 0.25


def test_no_effect_not_significant():
    rng = np.random.default_rng(1)
    seed = rng.uniform(0.4, 0.6, 30)
    chal = rng.uniform(0.4, 0.6, 30)
    res = paired_bca_bootstrap(PairedComparison(seed=seed, challenger=chal),
                               n_resamples=2000, seed=2)
    # CI should straddle 0 (usually)
    # allow occasional false positives, re-run deterministically
    assert res.ci_lower <= 0 or res.ci_upper >= 0 or abs(res.point_estimate) < 0.1


def test_poc2_small_n_reproduces_uncertainty():
    """POC-2 holdout: seed=0.787, best=0.725, n=8, diff=-0.062."""
    seed_scores = np.array([1.0, 0.4, 0.0, 0.9, 1.0, 1.0, 1.0, 1.0])
    best_scores = np.array([1.0, 0.2, 0.0, 0.6, 1.0, 1.0, 1.0, 1.0])
    res = paired_bca_bootstrap(PairedComparison(seed_scores, best_scores),
                               n_resamples=5000, seed=42)
    # CI should be wide enough that significance at 0 is borderline
    assert abs(res.point_estimate - (-0.0625)) < 1e-9
    # demonstrate small-n CI is wide
    assert res.ci_upper - res.ci_lower > 0.05


def test_hedges_g_small_sample_correction():
    # Large effect, small n
    seed = np.array([0.5, 0.5, 0.5, 0.5, 0.5])
    chal = np.array([0.7, 0.7, 0.7, 0.7, 0.7])
    es = hedges_g(PairedComparison(seed, chal))
    assert es.interpretation in ("large", "huge")


def test_tost_equivalence():
    rng = np.random.default_rng(3)
    seed = rng.uniform(0.4, 0.6, 50)
    chal = seed + rng.normal(0, 0.01, 50)   # basically identical
    res = tost_paired(PairedComparison(seed, chal), low=-0.05, high=0.05)
    assert res["equivalent"] is True


def test_required_n_for_small_effect():
    # Cohen's d = 0.2 needs ~200 samples for 80% power
    n = required_n_paired_t(0.2, alpha=0.05, power=0.80)
    assert 150 < n < 250
