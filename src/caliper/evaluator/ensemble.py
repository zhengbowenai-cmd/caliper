"""Multi-family ensemble judge with Krippendorff alpha + conservative reward.

Why ensemble
------------
Single-family judges exhibit self-preference bias (Panickssery et al.
2024) and collude with same-family targets over iterations. Using at
least three distinct families, with a conservative aggregator
`mean - lambda * std`, penalizes disagreement — so a challenger only
wins when *all* judges agree.

Reference: Coste-Anwar-Kirk-Krueger 2024, ICLR, "Reward Model Ensembles
Help Mitigate Overoptimization".

Krippendorff alpha (over a sliding window to stay responsive to drift)
monitors inter-rater reliability. If alpha drops below 0.5, the rubric
(or judge panel) is unreliable and must be recertified before further
promotion decisions.

Upgrades vs v1 (batch 1 quality debt)
-------------------------------------
- Judge output cache (in-memory by content hash) — halves API cost when
  the optimizer re-evaluates the same skill on the same cases.
- Sliding-window alpha (default last 50 rater-by-item rows).
- Explicit `parse_error` flag on JudgeVote — no more silent score=0.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import deque
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import krippendorff
import numpy as np

from caliper.runtime.llm import ChatMessage, LLMClient

log = logging.getLogger("caliper.evaluator.ensemble")


# ---------- judge protocol -----------------------------------------------


DEFAULT_JUDGE_PROMPT = """You are an impartial grader.

Task prompt:
<<<
{input}
>>>

Assistant response:
<<<
{response}
>>>

Principle being tested: {principle}

Scoring rubric (0-10 scale):
{rubric}

Return ONLY a JSON object, no markdown fences, exactly:
{{"score": <integer 0-10>, "feedback": "<1-3 sentences citing concrete parts of the response>"}}
"""


@dataclass
class JudgeVote:
    model_family: str
    model_id: str
    score: float  # normalized 0-1
    feedback: str
    parse_error: bool = False  # explicit flag so low scores can be distinguished from failures


@dataclass
class JudgeVerdict:
    per_vote: list[JudgeVote]
    mean: float
    std: float
    krippendorff_alpha: float | None
    conservative_score: float  # mean - lambda * std
    saturated: bool  # every vote >= saturation threshold
    disagreement_flag: bool  # std above disagreement threshold
    any_parse_error: bool  # at least one judge returned invalid JSON

    def as_dict(self) -> dict:
        return {
            "mean": self.mean,
            "std": self.std,
            "conservative_score": self.conservative_score,
            "krippendorff_alpha": self.krippendorff_alpha,
            "saturated": self.saturated,
            "disagreement_flag": self.disagreement_flag,
            "any_parse_error": self.any_parse_error,
            "per_vote": [
                dict(
                    model_family=v.model_family,
                    model_id=v.model_id,
                    score=v.score,
                    feedback=v.feedback,
                    parse_error=v.parse_error,
                )
                for v in self.per_vote
            ],
        }


# ---------- parsing ------------------------------------------------------


def _parse_judge_json(raw: str) -> tuple[float, str, bool]:
    """Returns (score_0_1, feedback, parse_error).

    parse_error=True iff the judge output wasn't valid JSON or lacked
    'score'. Callers must NOT treat a parse error as a legitimate low score.
    """
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    try:
        obj = json.loads(raw)
        score = float(obj["score"]) / 10.0
        fb = str(obj.get("feedback", ""))
        return max(0.0, min(1.0, score)), fb, False
    except Exception as e:
        return 0.0, f"[judge parse error: {e}] raw={raw[:200]!r}", True


# ---------- aggregator ---------------------------------------------------


@dataclass
class ConservativeReward:
    """Aggregates votes with `mean - lambda * std` penalty on disagreement."""

    lambda_disagreement: float = 0.5

    def __call__(self, scores: Sequence[float]) -> float:
        if len(scores) == 0:
            return 0.0
        scores = np.asarray(scores, dtype=float)
        return float(scores.mean() - self.lambda_disagreement * scores.std(ddof=0))


# ---------- cache key ----------------------------------------------------


def _cache_key(*, model_id: str, input_: str, response: str, principle: str, rubric: str) -> str:
    h = hashlib.sha256()
    h.update(model_id.encode("utf-8"))
    h.update(b"\x1f")
    for part in (input_, response, principle, rubric):
        h.update(part.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


# ---------- ensemble -----------------------------------------------------


@dataclass
class EnsembleJudge:
    judges: list[LLMClient]
    prompt_template: str = DEFAULT_JUDGE_PROMPT
    saturation_threshold: float = 0.95  # every vote >= this flags saturation
    disagreement_threshold: float = 0.20  # std > this triggers review
    aggregator: ConservativeReward = field(default_factory=ConservativeReward)
    parallel: bool = True
    alpha_window: int = 50  # sliding window for Krippendorff
    cache_enabled: bool = True
    _cache: dict[str, JudgeVote] = field(default_factory=dict, repr=False)
    _history: deque = field(default_factory=lambda: deque(maxlen=200), repr=False)

    def __post_init__(self):
        if len(self.judges) == 0:
            raise ValueError("EnsembleJudge needs >= 1 judge")
        # rewrap history deque to correct maxlen based on alpha_window
        object.__setattr__(self, "_history", deque(self._history, maxlen=max(2, self.alpha_window)))

    # ---- single-example scoring ---

    def score(self, *, input: str, response: str, principle: str, rubric: str) -> JudgeVerdict:
        prompt = self.prompt_template.format(
            input=input, response=response, principle=principle, rubric=rubric
        )
        votes: list[JudgeVote] = []

        def _ask(judge: LLMClient) -> JudgeVote:
            key = _cache_key(
                model_id=judge.model_id,
                input_=input,
                response=response,
                principle=principle,
                rubric=rubric,
            )
            if self.cache_enabled and key in self._cache:
                return self._cache[key]
            raw = judge.chat(
                [ChatMessage(role="user", content=prompt)],
                temperature=0.0,
                max_tokens=400,
            )
            score, fb, err = _parse_judge_json(raw)
            v = JudgeVote(
                model_family=judge.family,
                model_id=judge.model_id,
                score=score,
                feedback=fb,
                parse_error=err,
            )
            if self.cache_enabled and not err:
                self._cache[key] = v
            return v

        if self.parallel and len(self.judges) > 1:
            with ThreadPoolExecutor(max_workers=len(self.judges)) as ex:
                for v in ex.map(_ask, self.judges):
                    votes.append(v)
        else:
            votes = [_ask(j) for j in self.judges]

        # Sliding-window history: record only clean votes
        clean_scores = [v.score for v in votes if not v.parse_error]
        if clean_scores:
            self._history.append(clean_scores)

        return self._summarize(votes)

    # ---- history-driven reliability ---

    def _summarize(self, votes: list[JudgeVote]) -> JudgeVerdict:
        scores = [v.score for v in votes if not v.parse_error]
        any_err = any(v.parse_error for v in votes)

        if not scores:
            log.warning("EnsembleJudge: all judges parse-errored; returning 0 with flag")
            return JudgeVerdict(
                per_vote=votes,
                mean=0.0,
                std=0.0,
                krippendorff_alpha=None,
                conservative_score=0.0,
                saturated=False,
                disagreement_flag=False,
                any_parse_error=True,
            )

        arr = np.asarray(scores)
        mean = float(arr.mean())
        std = float(arr.std(ddof=0))
        conservative = self.aggregator(scores)
        saturated = bool(np.all(arr >= self.saturation_threshold))
        disagree = bool(std > self.disagreement_threshold)
        alpha = self._krippendorff_alpha_window()
        return JudgeVerdict(
            per_vote=votes,
            mean=mean,
            std=std,
            krippendorff_alpha=alpha,
            conservative_score=conservative,
            saturated=saturated,
            disagreement_flag=disagree,
            any_parse_error=any_err,
        )

    def _krippendorff_alpha_window(self) -> float | None:
        """alpha over recent alpha_window items only — responsive to drift."""
        if len(self._history) < 2:
            return None
        try:
            # filter to rows with same rater count
            n_raters = max(len(r) for r in self._history)
            clean = [r for r in self._history if len(r) == n_raters]
            if len(clean) < 2:
                return None
            mat = np.array([[round(s * 10) for s in row] for row in clean])
            # shape: (n_items, n_raters) -> krippendorff expects raters x items
            reliability_data = mat.T.astype(float)
            alpha = krippendorff.alpha(
                reliability_data=reliability_data,
                level_of_measurement="ordinal",
            )
            return float(alpha)
        except Exception as e:
            log.debug("Krippendorff calc failed: %s", e)
            return None

    def reset_history(self) -> None:
        self._history.clear()

    def clear_cache(self) -> None:
        self._cache.clear()

    def usage_summary(self) -> dict:
        """Return (calls, tokens) aggregated across judges."""
        out = {
            "judges": [j.usage_snapshot() for j in self.judges],
            "cache_size": len(self._cache),
            "history_len": len(self._history),
        }
        total_calls = sum(j.total_calls for j in self.judges)
        total_ptk = sum(j.total_prompt_tokens for j in self.judges)
        total_ctk = sum(j.total_completion_tokens for j in self.judges)
        out["total"] = dict(calls=total_calls, prompt_tokens=total_ptk, completion_tokens=total_ctk)
        return out

    @property
    def history(self) -> list[list[float]]:
        return list(self._history)
