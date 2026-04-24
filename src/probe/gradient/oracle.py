"""Programmatic pass/fail oracles — authoritative over LLM judges.

Rationale
---------
Whenever the correct answer can be *verified by code*, LLM judges are
unnecessary and risky (Goodhart, self-preference bias). The Oracle
Battery runs cheap checks first; LLM judges only tie-break when no
oracle applies.

This is intentionally simple — the point is composability. Each oracle
is a pure function: (input, response) -> OracleResult.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class OracleResult:
    passed: bool | None        # None = "not applicable to this case"
    detail: str = ""
    score: float | None = None   # optional 0-1 for partial credit


class OracleCheck(Protocol):
    """Any callable that takes (input, response) and returns OracleResult."""
    def __call__(self, input: str, response: str) -> OracleResult: ...


# ---------- concrete oracles ----------


@dataclass
class RegexOracle:
    """Pass iff `response` matches `must_match` AND does not match `must_not_match`."""
    must_match: str | None = None
    must_not_match: str | None = None
    flags: int = re.IGNORECASE | re.MULTILINE
    label: str = ""

    def __call__(self, input: str, response: str) -> OracleResult:
        reasons: list[str] = []
        if self.must_match is not None:
            if not re.search(self.must_match, response, self.flags):
                reasons.append(f"missing required pattern {self.must_match!r}")
        if self.must_not_match is not None:
            if re.search(self.must_not_match, response, self.flags):
                reasons.append(f"contains forbidden pattern {self.must_not_match!r}")
        if reasons:
            return OracleResult(passed=False, detail=f"[{self.label}] " + "; ".join(reasons))
        return OracleResult(passed=True, detail=f"[{self.label}] ok")


@dataclass
class LengthOracle:
    """Pass iff response length (char or word) is within [min, max]."""
    min_chars: int = 0
    max_chars: int = 10**9
    label: str = "length"

    def __call__(self, input: str, response: str) -> OracleResult:
        n = len(response)
        if n < self.min_chars:
            return OracleResult(passed=False,
                                detail=f"[{self.label}] {n} < min {self.min_chars}")
        if n > self.max_chars:
            return OracleResult(passed=False,
                                detail=f"[{self.label}] {n} > max {self.max_chars}")
        return OracleResult(passed=True,
                            detail=f"[{self.label}] {n} chars (within [{self.min_chars}, {self.max_chars}])")


@dataclass
class CallableOracle:
    """Wrap an arbitrary (input, response) -> bool | OracleResult callable."""
    fn: Callable[[str, str], bool | OracleResult]
    label: str = "custom"

    def __call__(self, input: str, response: str) -> OracleResult:
        out = self.fn(input, response)
        if isinstance(out, OracleResult):
            return out
        return OracleResult(passed=bool(out), detail=f"[{self.label}] {bool(out)}")


# ---------- battery ----------


@dataclass
class OracleBattery:
    """Run a list of oracles. Aggregates to overall pass/fail + partial score.

    Semantics:
      - If ANY oracle returns passed=False, overall=False.
      - If all applicable oracles pass, overall=True.
      - If no oracles applied, overall=None (fallback to LLM judge).
    """
    checks: list[OracleCheck]

    def run(self, input: str, response: str) -> tuple[OracleResult, list[OracleResult]]:
        per: list[OracleResult] = []
        applicable = 0
        any_fail = False
        for c in self.checks:
            r = c(input, response)
            per.append(r)
            if r.passed is None:
                continue
            applicable += 1
            if r.passed is False:
                any_fail = True

        if applicable == 0:
            return OracleResult(passed=None, detail="no applicable oracle"), per
        if any_fail:
            return OracleResult(
                passed=False,
                detail="; ".join(r.detail for r in per if r.passed is False),
                score=0.0,
            ), per
        return OracleResult(
            passed=True,
            detail="; ".join(r.detail for r in per if r.passed is True),
            score=1.0,
        ), per
