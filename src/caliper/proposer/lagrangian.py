"""Lagrangian length constraint with dual ascent.

We want candidate SKILL.md to respect hard length L_max (e.g. 1024 chars
for description, 6000 for body) without hard-rejecting slightly-over
candidates outright. Lagrangian primal-dual:

    reward_effective(x) = reward(x) - lambda * max(0, len(x) - L_max) ** 2

Dual update every round:
    lambda <- max(0, lambda + eta * (mean_len - L_max))

Stooke, Achiam, Abbeel 2020 — "Responsive Safety in RL by PID Lagrangian".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LagrangianLengthConstraint:
    l_max: int
    lam: float = 0.0
    eta: float = 1e-4
    clip_max: float = 10.0

    def penalty(self, length: int) -> float:
        over = max(0, length - self.l_max)
        return self.lam * (over**2)

    def adjusted_reward(self, reward: float, length: int) -> float:
        return reward - self.penalty(length)

    def update(self, mean_length: float) -> None:
        """Dual ascent: pull lambda up if we're over, down if under."""
        self.lam = max(0.0, min(self.clip_max, self.lam + self.eta * (mean_length - self.l_max)))
