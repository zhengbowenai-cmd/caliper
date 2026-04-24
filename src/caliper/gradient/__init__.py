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
    LengthOracle,
    OracleBattery,
    OracleCheck,
    OracleResult as OracleCheckResult,
    RegexOracle,
)
from caliper.gradient.replay import SectionSplit, counterfactual_ablation, split_skill_sections
from caliper.gradient.shapley import tmc_shapley

__all__ = [
    "LengthOracle",
    "OracleBattery",
    "OracleCheck",
    "OracleCheckResult",
    "RegexOracle",
    "SectionSplit",
    "counterfactual_ablation",
    "split_skill_sections",
    "tmc_shapley",
]
