"""Hedged-Capital Confidence Sequence for bounded [0,1] rewards.

References
----------
- Howard, Ramdas, McAuliffe, Sekhon (2021). "Time-uniform, nonparametric,
  nonasymptotic confidence sequences." Annals of Statistics 49(2).
- Waudby-Smith, Ramdas (2024). "Estimating means of bounded random
  variables by betting." JRSSB.

Why we need this
----------------
Traditional CI is valid only at a *pre-chosen* sample size. If you peek
every iteration and stop when the CI looks good, you inflate Type-I
error. A confidence sequence (CS) is valid at *every* stopping time
simultaneously — so peeking is free.

For the skill iteration loop: at every round, update the CS over val
scores. Promote only when CS lower bound strictly beats current champion.

Algorithm (Hedged Capital, Waudby-Smith & Ramdas 2024)
------------------------------------------------------
For bounded observations X_t in [0,1] and candidate mean m:
    K+_t(m) = prod_{i<=t} (1 + lambda_i * (X_i - m))   # testing mu <= m
    K-_t(m) = prod_{i<=t} (1 - lambda_i * (X_i - m))   # testing mu >= m
Both are nonnegative supermartingales under the respective null (Ville's
inequality). CS at level alpha:
    CS_t = { m in [0,1] : max(K+_t(m), K-_t(m)) < 1/alpha }

The betting fraction lambda_i is *predictable* (uses only X_{<i}). We
use the variance-adaptive schedule:
    lambda_t = min(c, sqrt(2 ln(2/alpha) / (sigmahat^2 * t * ln(1+t))))
clipped to [0, 1/(1-m) - epsilon] and [0, 1/m - epsilon] respectively so
capitals stay nonnegative.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from probe.schemas import CIResult


@dataclass
class HedgedCapitalCS:
    """Online CS: feed observations one at a time, read CI any time."""
    alpha: float = 0.05
    grid_size: int = 1001                      # m grid over [0,1]
    c_max: float = 0.75                        # max betting fraction (<1 for stability)

    _grid: np.ndarray = field(init=False, repr=False)
    _log_k_plus: np.ndarray = field(init=False, repr=False)   # log K+_t(m) for each m
    _log_k_minus: np.ndarray = field(init=False, repr=False)
    _running_sum: float = 0.0
    _running_sq: float = 0.0
    _n: int = 0

    def __post_init__(self):
        self._grid = np.linspace(0.0, 1.0, self.grid_size)
        self._log_k_plus = np.zeros(self.grid_size)
        self._log_k_minus = np.zeros(self.grid_size)

    # ---- online update --------------------------------------------------

    def update(self, x: float) -> None:
        """Absorb one observation x in [0,1]."""
        if not (0.0 <= x <= 1.0):
            raise ValueError(f"observation must be in [0,1], got {x}")

        # predictable betting fraction (uses past only)
        if self._n < 2:
            lam = 0.1
        else:
            var = max(1e-6, self._running_sq / self._n - (self._running_sum / self._n) ** 2)
            lam = float(np.sqrt(2.0 * np.log(2.0 / self.alpha) / (var * self._n * np.log(1 + self._n))))
            lam = min(lam, self.c_max)

        # for each candidate m, update log-capitals
        # clip lam per-m so terms stay positive
        eps = 1e-9
        # For K+: need 1 + lam * (x - m) > 0  =>  lam < 1/(m - x) if m > x, always ok if m <= x
        # Max safe lam for this t: min over m of the above; we just clip per-m.
        upper_plus = np.where(self._grid > x, 1.0 / np.maximum(self._grid - x, eps), 1e9)
        lam_plus = np.minimum(lam, 0.99 * upper_plus)

        upper_minus = np.where(self._grid < x, 1.0 / np.maximum(x - self._grid, eps), 1e9)
        lam_minus = np.minimum(lam, 0.99 * upper_minus)

        term_plus = 1.0 + lam_plus * (x - self._grid)
        term_minus = 1.0 - lam_minus * (x - self._grid)

        # guard against numerical zero (shouldn't hit after clipping)
        term_plus = np.maximum(term_plus, eps)
        term_minus = np.maximum(term_minus, eps)

        self._log_k_plus += np.log(term_plus)
        self._log_k_minus += np.log(term_minus)

        self._running_sum += x
        self._running_sq += x * x
        self._n += 1

    def update_many(self, xs) -> None:
        for x in xs:
            self.update(float(x))

    # ---- query ----------------------------------------------------------

    def ci(self) -> CIResult:
        """Return the current confidence interval.

        CS_t = {m : max(K+, K-) < 1/alpha} = {m : max(log K+, log K-) < -log(alpha)}
        """
        if self._n == 0:
            return CIResult(
                point_estimate=0.5,
                ci_lower=0.0, ci_upper=1.0,
                alpha=self.alpha, method="hedged_capital_cs", n=0,
                significant_at_zero=False,
            )

        thresh = -np.log(self.alpha)
        in_cs = (self._log_k_plus < thresh) & (self._log_k_minus < thresh)

        if not np.any(in_cs):
            # CS empty -> pathological; return full [0,1]
            lo, hi = 0.0, 1.0
        else:
            idx = np.where(in_cs)[0]
            lo = float(self._grid[idx[0]])
            hi = float(self._grid[idx[-1]])

        mean = self._running_sum / self._n
        # "significant" here = CS excludes the midpoint 0.5? Not standard.
        # We surface raw CI; downstream decides significance vs a champion.
        return CIResult(
            point_estimate=float(mean),
            ci_lower=lo, ci_upper=hi,
            alpha=self.alpha,
            method="hedged_capital_cs",
            n=self._n,
            significant_at_zero=(lo > 0 or hi < 0),
        )

    # ---- comparison gate ------------------------------------------------

    def dominates(self, champion_score: float, *, margin: float = 0.0) -> bool:
        """True iff our CS lower bound strictly beats champion + margin.

        This is the canonical 'peek-safe' promotion rule.
        """
        ci_ = self.ci()
        return ci_.ci_lower > champion_score + margin


# ---------------------- paired CS on difference ----------------------


@dataclass
class PairedDiffCS:
    """CS on the per-example score difference `challenger - seed`.

    For paired comparison we observe d_i = c_i - s_i in [-1, 1]. We affine-
    map to [0, 1] via u_i = (d_i + 1) / 2 and run a HedgedCapitalCS on u.
    The CS for the diff is then [2*u_lo - 1, 2*u_hi - 1], and "diff > 0"
    iff u > 0.5, i.e. CS_u excludes [0, 0.5].
    """
    alpha: float = 0.05
    _inner: HedgedCapitalCS = field(init=False, repr=False)

    def __post_init__(self):
        self._inner = HedgedCapitalCS(alpha=self.alpha)

    def update_pair(self, seed_score: float, challenger_score: float) -> None:
        d = challenger_score - seed_score
        u = (d + 1.0) / 2.0
        self._inner.update(u)

    def update_pairs(self, seeds, challengers) -> None:
        for s, c in zip(seeds, challengers):
            self.update_pair(float(s), float(c))

    def ci_diff(self) -> CIResult:
        ci_u = self._inner.ci()
        lo = 2 * ci_u.ci_lower - 1.0
        hi = 2 * ci_u.ci_upper - 1.0
        point = 2 * ci_u.point_estimate - 1.0
        return CIResult(
            point_estimate=point,
            ci_lower=lo, ci_upper=hi,
            alpha=self.alpha,
            method="hedged_capital_cs_paired",
            n=ci_u.n,
            significant_at_zero=(lo > 0 or hi < 0),
        )

    def challenger_wins(self, margin: float = 0.0) -> bool:
        """True iff CS lower bound on diff strictly > margin.

        Peek-safe: callable any time without inflating error.
        """
        ci_ = self.ci_diff()
        return ci_.ci_lower > margin
