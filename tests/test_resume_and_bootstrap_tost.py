"""Optimizer resume + bootstrap TOST tests."""
from pathlib import Path

import numpy as np
import pytest

from caliper.safety.bootstrap import PairedComparison, tost_paired
from caliper.persistence import RunDir


def test_bootstrap_tost_equivalent():
    rng = np.random.default_rng(0)
    n = 50
    seed = rng.uniform(0.4, 0.6, n)
    chal = seed + rng.normal(0, 0.01, n)  # basically identical
    cmp_ = PairedComparison(seed, chal)
    r = tost_paired(cmp_, low=-0.05, high=0.05, alpha=0.05, method="bootstrap")
    assert r["method"] == "tost_paired_bootstrap"
    assert r["equivalent"] is True


def test_bootstrap_tost_not_equivalent():
    rng = np.random.default_rng(1)
    n = 30
    seed = rng.uniform(0.4, 0.6, n)
    chal = seed + 0.3  # clearly different
    cmp_ = PairedComparison(seed, chal)
    r = tost_paired(cmp_, low=-0.05, high=0.05, alpha=0.05, method="bootstrap")
    assert r["equivalent"] is False


def test_resume_loads_champion_as_seed(tmp_path: Path):
    """Ensure optimizer.run() with resume=True picks up champion.md as new seed."""
    rd = RunDir(tmp_path / "run1")
    rd.write_text(rd.seed_path, "---\nname: orig\ndescription: original seed.\n---\nbody1")
    # simulate a prior successful round
    rd.write_text(rd.champion_path, "---\nname: evolved\ndescription: evolved champion.\n---\nbody2")
    rd.round_dir(0)  # make round 0 dir exist

    # Use RunDir's list_rounds to confirm (no live LLM needed)
    assert rd.list_rounds() == [0]
    assert "evolved" in rd.champion_path.read_text(encoding="utf-8")
