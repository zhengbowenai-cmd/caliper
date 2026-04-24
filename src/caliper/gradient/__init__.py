"""Gradient Source Layer — produces attribution signals algorithmically,
NOT via LLM self-reflection.

Replaces the broken assumption that LLM reflection can localize failures
(AgenTracer/MAST empirical finding: <10% attribution accuracy).

Three tools:
  - oracle    Programmatic pass/fail checks (authoritative over LLM judges)
  - replay    Counterfactual ablation — remove skill section, re-evaluate
  - shapley   TMC Shapley — Monte Carlo attribution across sections
"""
from caliper.gradient.oracle import (
    OracleResult as OracleCheckResult,
    OracleCheck,
    RegexOracle,
    LengthOracle,
    OracleBattery,
)
from caliper.gradient.replay import SectionSplit, split_skill_sections, counterfactual_ablation
from caliper.gradient.shapley import tmc_shapley

__all__ = [
    "OracleCheckResult", "OracleCheck", "RegexOracle", "LengthOracle",
    "OracleBattery",
    "SectionSplit", "split_skill_sections", "counterfactual_ablation",
    "tmc_shapley",
]
