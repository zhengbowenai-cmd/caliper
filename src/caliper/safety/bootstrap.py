"""Paired bootstrap + effect size, calibrated for small-n LLM eval.

References
----------
- Efron, B. (1987). "Better bootstrap confidence intervals." JASA 82.
- Koehn, P. (2004). "Statistical significance tests for MT evaluation." EMNLP.
- Hedges, L.V. (1981). "Distribution theory for Glass's estimator of
  effect size." J. Educ. Stat. 6.

Motivation
----------
POC-2 reported "+17% val improvement" on n=8. Without a CI + effect size,
that number is narrative, not evidence. This module produces proper
paired BCa CI, Hedges' g (small-sample bias-corrected), and TOST
equivalence-test p-values.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats

from caliper.schemas import CIResult, EffectSize


@dataclass
class PairedComparison:
    """Per-example score pairs (seed vs challenger)."""

    seed: np.ndarray  # shape (n,)
    challenger: np.ndarray  # shape (n,)

    def __post_init__(self):
        self.seed = np.asarray(self.seed, dtype=float)
        self.challenger = np.asarray(self.challenger, dtype=float)
        if self.seed.shape != self.challenger.shape:
            raise ValueError(f"shape mismatch: {self.seed.shape} vs {self.challenger.shape}")
        if self.seed.ndim != 1:
            raise ValueError("expect 1D arrays")

    @property
    def n(self) -> int:
        return len(self.seed)

    @property
    def diff(self) -> np.ndarray:
        return self.challenger - self.seed

    @property
    def mean_diff(self) -> float:
        return float(self.diff.mean())


# ------------------------------------------------------------------
# BCa paired bootstrap — Efron 1987, bias + acceleration corrected
# ------------------------------------------------------------------


def paired_bca_bootstrap(
    cmp: PairedComparison,
    *,
    n_resamples: int = 10_000,
    alpha: float = 0.05,
    seed: int = 0,
) -> CIResult:
    """Paired BCa bootstrap CI on the mean score difference.

    scipy.stats.bootstrap implements BCa; we wrap it with a paired
    statistic. Returns a CIResult with significant_at_zero = CI excludes 0.
    """
    if cmp.n < 3:
        raise ValueError("BCa needs n >= 3; got n=%d" % cmp.n)

    rng = np.random.default_rng(seed)

    # scipy's bootstrap accepts a tuple of arrays; statistic receives
    # resampled arrays *paired by index* when paired=True.
    res = stats.bootstrap(
        (cmp.seed, cmp.challenger),
        statistic=lambda s, c: float(np.mean(c - s)),
        n_resamples=n_resamples,
        confidence_level=1 - alpha,
        method="BCa",
        paired=True,
        vectorized=False,
        random_state=rng,
    )

    lo, hi = float(res.confidence_interval.low), float(res.confidence_interval.high)

    # Handle degenerate data (all diffs identical → BCa returns NaN)
    if np.isnan(lo) or np.isnan(hi):
        # Fall back to a trivial CI anchored at the observed mean
        lo = hi = cmp.mean_diff
        method = "bca_bootstrap_degenerate"
    else:
        method = "bca_bootstrap"

    return CIResult(
        point_estimate=cmp.mean_diff,
        ci_lower=lo,
        ci_upper=hi,
        alpha=alpha,
        method=method,
        n=cmp.n,
        significant_at_zero=(lo > 0) or (hi < 0),
    )


# ------------------------------------------------------------------
# Hedges' g with small-sample correction (paired)
# ------------------------------------------------------------------


def hedges_g(cmp: PairedComparison) -> EffectSize:
    """Paired Hedges' g (bias-corrected Cohen's d_z for small samples).

    g = d_z * J(df),  d_z = mean(diff) / sd(diff),  J(df) = 1 - 3/(4df-1)
    """
    d = cmp.diff
    sd = d.std(ddof=1)
    if sd == 0:
        # Zero-variance diff: all pairs moved by the same amount.
        # By convention, treat as infinite effect in direction of mean.
        mean = float(d.mean())
        if mean == 0:
            g = 0.0
        else:
            # Large finite surrogate so downstream interpretation is "huge".
            g = float(np.sign(mean) * 10.0)
    else:
        d_z = d.mean() / sd
        df = cmp.n - 1
        J = 1.0 - 3.0 / (4 * df - 1) if df > 0 else 1.0  # small-sample bias correction
        g = float(d_z * J)

    return EffectSize(hedges_g=g, interpretation=effect_size_interpretation(g))


def effect_size_interpretation(g: float):
    """Cohen 1988 thresholds for d/g."""
    a = abs(g)
    if a < 0.2:
        return "negligible"
    if a < 0.5:
        return "small"
    if a < 0.8:
        return "medium"
    if a < 1.2:
        return "large"
    return "huge"


# ------------------------------------------------------------------
# TOST — Two One-Sided Tests for equivalence
# ------------------------------------------------------------------


def tost_paired(
    cmp: PairedComparison,
    *,
    low: float = -0.05,
    high: float = 0.05,
    alpha: float = 0.05,
    method: str = "t",
) -> dict:
    """Paired TOST: test whether mean diff is within [low, high] bounds.

    If both one-sided tests reject at `alpha`, we conclude equivalence.
    Reference: Schuirmann 1987; Lakens 2017.

    method:
      "t" (default) — parametric t-distribution; assumes normal diffs.
                      Works OK for unimodal approximately-normal scores.
      "bootstrap"   — percentile bootstrap of the mean. Distribution-free.
                      Preferred for bounded [0,1] scores where t is suspect.

    Returns dict with p_low, p_high, equivalent (bool).
    """
    if method == "bootstrap":
        return _tost_paired_bootstrap(cmp, low=low, high=high, alpha=alpha)
    return _tost_paired_t(cmp, low=low, high=high, alpha=alpha)


def _tost_paired_t(cmp: PairedComparison, *, low: float, high: float, alpha: float) -> dict:
    d = cmp.diff
    n = len(d)
    mean = float(d.mean())
    se = float(d.std(ddof=1) / np.sqrt(n)) if n > 1 else float("inf")

    if se == 0:
        # deterministic
        equivalent = low <= mean <= high
        return dict(
            mean_diff=mean,
            p_low=0.0 if mean > low else 1.0,
            p_high=0.0 if mean < high else 1.0,
            equivalent=equivalent,
            method="tost_paired_deterministic",
        )

    # H01: diff <= low  (test from above)
    t_low = (mean - low) / se
    p_low = 1.0 - float(stats.t.cdf(t_low, df=n - 1))

    # H02: diff >= high (test from below)
    t_high = (mean - high) / se
    p_high = float(stats.t.cdf(t_high, df=n - 1))

    equivalent = (p_low < alpha) and (p_high < alpha)
    return dict(
        mean_diff=mean,
        p_low=p_low,
        p_high=p_high,
        equivalent=equivalent,
        method="tost_paired_t",
        ci_equivalence_bounds=(low, high),
    )


def _tost_paired_bootstrap(
    cmp: PairedComparison,
    *,
    low: float,
    high: float,
    alpha: float,
    n_resamples: int = 5000,
    seed: int = 0,
) -> dict:
    """Distribution-free TOST via percentile bootstrap.

    Strategy: bootstrap the mean diff B times. Equivalent iff (1-2α) CI of
    bootstrap distribution is strictly inside (low, high).
    """
    rng = np.random.default_rng(seed)
    d = cmp.diff
    n = len(d)
    means = np.empty(n_resamples)
    for i in range(n_resamples):
        idx = rng.integers(0, n, n)
        means[i] = d[idx].mean()
    # (1 - 2*alpha) CI (Schuirmann 1987: 90% CI for α=0.05)
    lo_q, hi_q = np.percentile(means, [100 * alpha, 100 * (1 - alpha)])
    equivalent = (low < lo_q) and (hi_q < high)
    return dict(
        mean_diff=float(d.mean()),
        ci_lower_1m2a=float(lo_q),
        ci_upper_1m2a=float(hi_q),
        equivalent=bool(equivalent),
        method="tost_paired_bootstrap",
        ci_equivalence_bounds=(low, high),
    )


# ------------------------------------------------------------------
# Power analysis — n needed to detect given effect size
# ------------------------------------------------------------------


def required_n_paired_t(
    effect_size_d: float,
    *,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Approximate n for paired t-test (two-sided).

    n ≈ ((z_{1-α/2} + z_{1-β}) / d)^2,  rounded up and >= 4.
    """
    if effect_size_d <= 0:
        return int(1e9)
    z_alpha = float(stats.norm.ppf(1 - alpha / 2))
    z_beta = float(stats.norm.ppf(power))
    n = ((z_alpha + z_beta) / effect_size_d) ** 2
    return max(4, int(np.ceil(n)))
