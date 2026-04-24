"""Unified data contract — every component ingests/emits SkillRun."""
from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class TraceStep(BaseModel):
    role: str
    content: str
    tool_used: str | None = None
    tokens: int | None = None


class JudgeScore(BaseModel):
    model_family: str                          # "claude" | "qwen" | "deepseek" | ...
    model_id: str
    rubric_item_id: str
    score: float = Field(ge=0.0, le=1.0)       # normalized 0-1
    raw_feedback: str = ""


class UserSignal(BaseModel):
    """Real ground-truth signals from Claude Code hooks."""
    accepted: bool | None = None
    undone: bool | None = None
    retried_immediately: bool | None = None    # strongest negative signal
    latency_ms: int | None = None


class OracleResult(BaseModel):
    """Programmatic check; if present, authoritative."""
    passed: bool
    detail: str = ""


class SkillRun(BaseModel):
    """The unified schema every probe component speaks."""
    id: str
    skill_version_hash: str
    input: str
    response: str
    trace: list[TraceStep] = []
    oracle: OracleResult | None = None
    judges: list[JudgeScore] = []
    theta_irt: float | None = None             # IRT latent ability
    user_signal: UserSignal | None = None
    shapley: dict[str, float] = {}             # section_id -> phi_i
    cf_diff: dict[str, str] = {}               # section_id -> counterfactual content
    meta: dict[str, Any] = {}


class CIResult(BaseModel):
    """Confidence interval produced by bootstrap/CS."""
    point_estimate: float
    ci_lower: float
    ci_upper: float
    alpha: float = 0.05
    method: str                                # "bca_bootstrap" | "hedged_capital_cs" | ...
    n: int
    significant_at_zero: bool                  # CI excludes zero (two-sided)


class EffectSize(BaseModel):
    hedges_g: float
    interpretation: Literal["negligible", "small", "medium", "large", "huge"]
    # Cohen thresholds for hedges g: 0.2/0.5/0.8


class Decision(BaseModel):
    """Output of the Safety layer gate."""
    accept: bool
    reason: str
    evidence: dict[str, Any]
