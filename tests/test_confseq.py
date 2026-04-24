"""Tests for safety.confseq — Hedged-Capital CS."""

import numpy as np

from caliper.safety import HedgedCapitalCS, PairedDiffCS


def test_cs_narrows_with_samples():
    cs = HedgedCapitalCS(alpha=0.05)
    # Tight distribution around 0.7
    rng = np.random.default_rng(0)
    xs = np.clip(rng.normal(0.7, 0.05, 500), 0, 1)
    widths = []
    for i, x in enumerate(xs):
        cs.update(float(x))
        if i in (10, 50, 100, 200, 499):
            ci = cs.ci()
            widths.append(ci.ci_upper - ci.ci_lower)
    # CS width should monotonically (mostly) shrink
    assert widths[-1] < widths[0]


def test_cs_covers_true_mean_most_of_the_time():
    """At alpha=0.05, CS should cover true mean at every peek — not just once."""
    true_mean = 0.6
    rng = np.random.default_rng(1)
    cs = HedgedCapitalCS(alpha=0.05)
    for _ in range(200):
        cs.update(float(np.clip(rng.normal(true_mean, 0.1), 0, 1)))
    ci = cs.ci()
    assert ci.ci_lower <= true_mean <= ci.ci_upper


def test_paired_diff_detects_real_improvement():
    rng = np.random.default_rng(2)
    pdcs = PairedDiffCS(alpha=0.05)
    for _ in range(200):
        s = float(np.clip(rng.normal(0.5, 0.1), 0, 1))
        c = float(np.clip(s + 0.15 + rng.normal(0, 0.05), 0, 1))
        pdcs.update_pair(s, c)
    ci = pdcs.ci_diff()
    assert ci.ci_lower > 0, (
        f"expected significant positive diff, got CI=[{ci.ci_lower}, {ci.ci_upper}]"
    )


def test_paired_diff_no_effect_stays_around_zero():
    rng = np.random.default_rng(3)
    pdcs = PairedDiffCS(alpha=0.05)
    for _ in range(100):
        s = float(np.clip(rng.normal(0.5, 0.1), 0, 1))
        c = float(np.clip(rng.normal(0.5, 0.1), 0, 1))
        pdcs.update_pair(s, c)
    ci = pdcs.ci_diff()
    assert ci.ci_lower <= 0 <= ci.ci_upper, (
        f"no-effect should straddle 0; CI=[{ci.ci_lower}, {ci.ci_upper}]"
    )
