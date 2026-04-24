"""Tests for governance.budget."""

import time

import pytest

from caliper.governance.budget import Budget, BudgetExceeded, estimate_cost_cny


class _MockClient:
    def __init__(self, family, ptok=0, ctok=0):
        self.family = family
        self.total_prompt_tokens = ptok
        self.total_completion_tokens = ctok


def test_rounds_limit():
    b = Budget(max_rounds=2)
    b.tick_round()
    b.tick_round()
    with pytest.raises(BudgetExceeded, match="max_rounds"):
        b.tick_round()


def test_token_limit():
    b = Budget(max_tokens=100)
    clients = [_MockClient("qwen", ptok=50, ctok=30)]
    b.check(clients)  # ok
    clients[0].total_completion_tokens = 60
    with pytest.raises(BudgetExceeded, match="tokens"):
        b.check(clients)


def test_cost_limit_cny():
    b = Budget(max_cost_cny=0.10)  # 0.1 yuan
    # qwen: 8 CNY/Mtok in, 24 CNY/Mtok out
    # 5000 prompt + 5000 completion = 0.04 + 0.12 = 0.16 yuan
    clients = [_MockClient("qwen", ptok=5000, ctok=5000)]
    with pytest.raises(BudgetExceeded, match="cost"):
        b.check(clients)


def test_snapshot_does_not_raise():
    b = Budget(max_tokens=10)
    clients = [_MockClient("qwen", ptok=1000, ctok=1000)]
    snap = b.snapshot(clients)
    assert snap["tokens"] == 2000  # snapshot shows actual, no raise
    assert snap["limits"]["tokens"] == 10


def test_cost_estimate_formula():
    # 1M input tokens + 1M output tokens on qwen
    c = estimate_cost_cny("qwen", 1_000_000, 1_000_000)
    assert abs(c - (8.0 + 24.0)) < 0.01


def test_wallclock_limit():
    b = Budget(max_wallclock_s=0.05)
    time.sleep(0.1)
    with pytest.raises(BudgetExceeded, match="wallclock"):
        b.check([])
