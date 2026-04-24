"""Cost + wallclock + round budget governor.

Why it matters
--------------
Self-iterating agents without budget ceilings can burn money on
non-productive loops (AI Scientist precedent, Beel et al. 2025).
Budget enforcement must live OUTSIDE the optimizer process — the
Optimizer polls Budget between gates; Budget says stop, Optimizer stops.

We track three exhaustable resources:
  - wallclock   seconds elapsed since start
  - tokens      sum prompt_tokens + completion_tokens across all LLMs
  - yuan/$      computed from per-family rate tables
  - rounds      max proposal rounds

Any limit hit → BudgetExceeded with reason, causing the optimizer to
finalize with current champion (no forced rollback).
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from dataclasses import dataclass, field


class BudgetExceeded(Exception):
    pass


# Per-million-token rates (CNY). Rough order-of-magnitude; adjust per provider.
# Conservative defaults so we overestimate rather than surprise.
_DEFAULT_RATES_CNY_PER_MTOK = {
    ("qwen", "input"): 8.0,  # qwen-max input
    ("qwen", "output"): 24.0,  # qwen-max output
    ("deepseek", "input"): 2.0,
    ("deepseek", "output"): 8.0,
    ("claude", "input"): 22.0,  # sonnet
    ("claude", "output"): 110.0,
    ("gpt", "input"): 18.0,
    ("gpt", "output"): 60.0,
    ("unknown", "input"): 20.0,
    ("unknown", "output"): 60.0,
}


def estimate_cost_cny(
    family: str, prompt_tok: int, completion_tok: int, rates: dict | None = None
) -> float:
    r = rates or _DEFAULT_RATES_CNY_PER_MTOK
    fam = family.lower() if family else "unknown"
    in_rate = r.get((fam, "input")) or r[("unknown", "input")]
    out_rate = r.get((fam, "output")) or r[("unknown", "output")]
    return (prompt_tok * in_rate + completion_tok * out_rate) / 1_000_000.0


@dataclass
class Budget:
    max_wallclock_s: float | None = None
    max_tokens: int | None = None
    max_cost_cny: float | None = None
    max_rounds: int | None = None
    rates: dict | None = None
    _start_time: float = field(default_factory=time.monotonic, init=False)
    _round_count: int = field(default=0, init=False)

    def tick_round(self) -> None:
        self._round_count += 1
        if self.max_rounds is not None and self._round_count > self.max_rounds:
            raise BudgetExceeded(f"max_rounds {self.max_rounds} exceeded")

    def check(self, llm_clients: Iterable) -> None:
        """Raise BudgetExceeded if any limit hit.

        llm_clients: any iterable with .total_prompt_tokens /
        .total_completion_tokens / .family attributes.
        """
        # wallclock
        elapsed = time.monotonic() - self._start_time
        if self.max_wallclock_s is not None and elapsed > self.max_wallclock_s:
            raise BudgetExceeded(f"wallclock {elapsed:.0f}s > limit {self.max_wallclock_s}s")
        # tokens
        total_tokens = sum(
            getattr(c, "total_prompt_tokens", 0) + getattr(c, "total_completion_tokens", 0)
            for c in llm_clients
        )
        if self.max_tokens is not None and total_tokens > self.max_tokens:
            raise BudgetExceeded(f"tokens {total_tokens:,} > limit {self.max_tokens:,}")
        # cost
        if self.max_cost_cny is not None:
            total_cost = 0.0
            for c in llm_clients:
                total_cost += estimate_cost_cny(
                    getattr(c, "family", "unknown"),
                    getattr(c, "total_prompt_tokens", 0),
                    getattr(c, "total_completion_tokens", 0),
                    rates=self.rates,
                )
            if total_cost > self.max_cost_cny:
                raise BudgetExceeded(
                    f"estimated cost ¥{total_cost:.2f} > limit ¥{self.max_cost_cny:.2f}"
                )

    def snapshot(self, llm_clients: Iterable) -> dict:
        """Status for logging/display (does NOT raise)."""
        elapsed = time.monotonic() - self._start_time
        clients = list(llm_clients)
        tokens = sum(
            getattr(c, "total_prompt_tokens", 0) + getattr(c, "total_completion_tokens", 0)
            for c in clients
        )
        cost = sum(
            estimate_cost_cny(
                getattr(c, "family", "unknown"),
                getattr(c, "total_prompt_tokens", 0),
                getattr(c, "total_completion_tokens", 0),
                rates=self.rates,
            )
            for c in clients
        )
        return dict(
            wallclock_s=round(elapsed, 1),
            tokens=tokens,
            cost_cny_est=round(cost, 3),
            rounds_used=self._round_count,
            limits=dict(
                wallclock_s=self.max_wallclock_s,
                tokens=self.max_tokens,
                cost_cny=self.max_cost_cny,
                rounds=self.max_rounds,
            ),
        )
