"""Tests for gradient layer: oracle, replay, shapley."""
import re

import pytest

from probe.gradient import (
    OracleBattery,
    RegexOracle,
    LengthOracle,
    counterfactual_ablation,
    split_skill_sections,
    tmc_shapley,
)
from probe.gradient.oracle import OracleResult


# ---------- oracle ----------


def test_regex_oracle_pass():
    o = RegexOracle(must_match=r"hello", label="greet")
    r = o("ignored", "say hello world")
    assert r.passed is True


def test_regex_oracle_fail():
    o = RegexOracle(must_not_match=r"bug", label="no-bug")
    r = o("x", "there is a BUG here")
    assert r.passed is False
    assert "forbidden" in r.detail


def test_length_oracle():
    o = LengthOracle(min_chars=5, max_chars=20)
    assert o("x", "short").passed is True
    assert o("x", "!!").passed is False           # too short
    assert o("x", "x" * 21).passed is False       # too long


def test_battery_overall_fail_on_any():
    battery = OracleBattery(checks=[
        RegexOracle(must_match=r"hello", label="greet"),
        LengthOracle(max_chars=5, label="short"),
    ])
    overall, per = battery.run("x", "hello world")  # passes greet, fails short
    assert overall.passed is False


def test_battery_no_applicable():
    """If every oracle returns None, overall is None (fall through to LLM)."""
    from probe.gradient.oracle import CallableOracle
    o = CallableOracle(fn=lambda i, r: OracleResult(passed=None, detail="n/a"))
    battery = OracleBattery(checks=[o])
    overall, _ = battery.run("x", "y")
    assert overall.passed is None


# ---------- section split / replay ----------


SAMPLE_SKILL = """---
name: test
description: test skill.
---

This is a preamble.

# Section One

Body of section one.

# Section Two

Body of section two.
Multi-line.

# Section Three

Final section.
"""


def test_split_finds_sections():
    split = split_skill_sections(SAMPLE_SKILL)
    assert len(split.sections) == 3
    assert split.sections[0][0] == "# Section One"
    assert split.sections[1][0] == "# Section Two"
    assert "preamble" in split.preamble


def test_split_rebuild_identity():
    split = split_skill_sections(SAMPLE_SKILL)
    assert split.rebuild() == SAMPLE_SKILL


def test_split_rebuild_without():
    split = split_skill_sections(SAMPLE_SKILL)
    without_two = split.rebuild_without(1)
    assert "# Section One" in without_two
    assert "# Section Two" not in without_two
    assert "# Section Three" in without_two


def test_counterfactual_ablation_signs():
    """Section that mentions 'keyword' helps; removing it hurts."""
    md = """---
name: t
description: t.
---

# A

keyword important

# B

nothing special here
"""
    def scorer(s: str) -> float:
        return 1.0 if "keyword" in s else 0.2

    ace = counterfactual_ablation(md, scorer)
    assert ace["# A"] > 0    # removing A hurts
    assert abs(ace["# B"]) < 1e-9   # removing B doesn't change score


# ---------- shapley ----------


def test_shapley_efficiency_property():
    """Sum of phi = v(full) - v(empty), within MC noise."""
    md = """---
name: t
description: t.
---

# A

alpha

# B

beta

# C

gamma
"""
    def scorer(s: str) -> float:
        # score = count of included keywords
        return sum(k in s for k in ["alpha", "beta", "gamma"]) / 3.0

    full = scorer(md)
    empty_md = split_skill_sections(md).rebuild()  # same full
    # v(empty) = score with no sections
    from probe.gradient.replay import split_skill_sections as _s
    split = _s(md)
    v_empty = scorer(split.frontmatter + split.preamble)

    phi = tmc_shapley(md, scorer, num_permutations=30, seed=1)
    assert abs(sum(phi.values()) - (full - v_empty)) < 0.05


def test_shapley_all_equal_for_symmetric_skill():
    """Three symmetric sections each contribute equally."""
    md = """---
name: t
description: t.
---

# A

hello

# B

hello

# C

hello
"""
    def scorer(s: str) -> float:
        return s.count("hello") / 3.0

    phi = tmc_shapley(md, scorer, num_permutations=50, seed=2)
    vals = list(phi.values())
    # each should be ~1/3, tolerance for MC
    for v in vals:
        assert 0.2 < v < 0.5
