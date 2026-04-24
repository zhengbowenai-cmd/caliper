"""Optimizer — orchestrates the full gate chain.

One `run()` call executes multiple rounds of propose → lint → eval →
statistical decide. Every round's artifacts land in the RunDir. State is
JSON-persistent so a run can be resumed or audited externally.

Gate order (rejection at ANY gate kills the candidate, champion stands):
  1. Linter        — HIGH findings block
  2. Judge panel   — produce SkillRun per eval case
  3. Bootstrap CI  — BCa paired CI on (champion, candidate) scores
  4. Confidence Seq — CS lower bound on diff must exceed margin
  5. (Effect size reported as context — not a gate)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np

from caliper.evaluator.ensemble import EnsembleJudge, JudgeVerdict
from caliper.governance.budget import Budget, BudgetExceeded
from caliper.persistence import RunDir, make_skill_run
from caliper.proposer.lagrangian import LagrangianLengthConstraint
from caliper.proposer.linter import LintFinding, RuleConflictLinter, Severity
from caliper.proposer.rewriter import NaiveRewriter
from caliper.runtime.llm import ChatMessage, LLMClient
from caliper.safety.bootstrap import (
    PairedComparison,
    hedges_g,
    paired_bca_bootstrap,
)
from caliper.safety.confseq import PairedDiffCS
from caliper.schemas import CIResult, Decision, EffectSize, SkillRun

log = logging.getLogger("caliper.optimizer")


# ---------- eval case schema ----------


@dataclass
class EvalCase:
    id: str
    input: str
    principle: str
    rubric: str


def load_eval_jsonl(path: str | Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        cases.append(EvalCase(
            id=row["id"],
            input=row["input"],
            principle=row.get("principle", ""),
            rubric=row.get("rubric", ""),
        ))
    return cases


# ---------- config & result ----------


@dataclass
class OptimizerConfig:
    max_rounds: int = 3
    cs_margin: float = 0.02          # CS lower bound on diff must exceed this
    bootstrap_n_resamples: int = 5000
    bootstrap_alpha: float = 0.05
    cs_alpha: float = 0.05
    description_char_limit: int = 1024
    body_char_limit: int = 6000
    # Number of candidates to generate per round (just 1 for MVP)
    candidates_per_round: int = 1
    # Lagrangian length constraint — penalty on adjusted_reward for > body_char_limit
    lagrangian_eta: float = 1e-4
    # Budget caps (optional; None = unlimited). Set via CLI.
    max_wallclock_s: float | None = None
    max_tokens: int | None = None
    max_cost_cny: float | None = None


@dataclass
class RoundReport:
    round_num: int
    candidate_md: str
    lint_findings: list[LintFinding]
    lint_blocked: bool
    skill_runs_seed: list[SkillRun]       # champion's runs on same cases
    skill_runs_candidate: list[SkillRun]
    seed_scores: list[float]
    candidate_scores: list[float]
    bootstrap_ci: CIResult | None
    effect_size: EffectSize | None
    cs_ci: CIResult | None
    decision: Decision

    def summary(self) -> dict:
        return {
            "round": self.round_num,
            "lint_blocked": self.lint_blocked,
            "lint_high": sum(1 for f in self.lint_findings
                             if f.severity == Severity.HIGH),
            "seed_mean": float(np.mean(self.seed_scores)) if self.seed_scores else None,
            "cand_mean": float(np.mean(self.candidate_scores)) if self.candidate_scores else None,
            "ci": self.bootstrap_ci.model_dump() if self.bootstrap_ci else None,
            "hedges_g": self.effect_size.hedges_g if self.effect_size else None,
            "cs_ci": self.cs_ci.model_dump() if self.cs_ci else None,
            "accept": self.decision.accept,
            "reason": self.decision.reason,
        }


@dataclass
class OptimizerResult:
    champion_md: str
    champion_hash: str
    rounds: list[RoundReport] = field(default_factory=list)
    final_decision: Decision | None = None


# ---------- orchestrator ----------


@dataclass
class Optimizer:
    target_lm: LLMClient                   # the LLM being instructed
    judges: EnsembleJudge
    rewriter: NaiveRewriter
    linter: RuleConflictLinter = field(default_factory=RuleConflictLinter)
    config: OptimizerConfig = field(default_factory=OptimizerConfig)
    _lagrangian: LagrangianLengthConstraint = field(init=False, repr=False)
    _budget: Budget = field(init=False, repr=False)

    def __post_init__(self):
        self._lagrangian = LagrangianLengthConstraint(
            l_max=self.config.body_char_limit,
            eta=self.config.lagrangian_eta,
        )
        self._budget = Budget(
            max_wallclock_s=self.config.max_wallclock_s,
            max_tokens=self.config.max_tokens,
            max_cost_cny=self.config.max_cost_cny,
            max_rounds=self.config.max_rounds,
        )

    # ---- all LLM clients we manage (for budget polling) ----

    def _all_llms(self):
        yield self.target_lm
        for j in self.judges.judges:
            yield j

    # ---- main entry ----

    def run(
        self,
        seed_md: str,
        eval_cases: list[EvalCase],
        run_dir: str | Path,
        progress: Callable[[str], None] | None = None,
        resume: bool = False,
    ) -> OptimizerResult:
        rd = RunDir(run_dir)
        # Resume: if run_dir exists with a champion.md, load it as champion
        resumed_from_round = -1
        if resume and rd.champion_path.exists():
            existing_champ = rd.champion_path.read_text(encoding="utf-8")
            if existing_champ.strip():
                seed_md = existing_champ  # treat existing champion as new seed
                resumed_from_round = max(rd.list_rounds(), default=-1)
        rd.write_text(rd.seed_path, seed_md)
        rd.write_json(rd.config_path, self.config)

        def log_(msg: str) -> None:
            if progress:
                progress(msg)
            log.info(msg)

        if resumed_from_round >= 0:
            log_(f"[caliper] RESUMING from run_dir (last round {resumed_from_round}); "
                 f"champion promoted to seed.")
        log_(f"[caliper] starting run with {len(eval_cases)} eval cases, max_rounds={self.config.max_rounds}")
        log_(f"[caliper] budget limits = {self._budget.snapshot(self._all_llms())['limits']}")

        # evaluate seed once (champion baseline)
        log_(f"[caliper] evaluating seed (champion) on {len(eval_cases)} cases...")
        seed_runs = self._eval_skill(seed_md, eval_cases)
        seed_scores = [self._run_score(r) for r in seed_runs]
        log_(f"[caliper] seed mean = {np.mean(seed_scores):.3f}")
        try:
            self._budget.check(self._all_llms())
        except BudgetExceeded as e:
            log_(f"[caliper] budget exceeded during seed eval: {e}")

        champion_md = seed_md
        champion_scores = seed_scores
        champion_runs = seed_runs
        rd.write_text(rd.champion_path, champion_md)

        reports: list[RoundReport] = []
        pdcs = PairedDiffCS(alpha=self.config.cs_alpha)

        for i in range(self.config.max_rounds):
            # ---- budget gate before each round ----
            try:
                self._budget.tick_round()
                self._budget.check(self._all_llms())
            except BudgetExceeded as e:
                log_(f"[caliper] stopping: {e}")
                break

            snap = self._budget.snapshot(self._all_llms())
            log_(f"[caliper] ─── round {i} ─── "
                 f"elapsed={snap['wallclock_s']}s tokens={snap['tokens']:,} "
                 f"cost=¥{snap['cost_cny_est']:.2f}")

            # ---- propose ----
            judge_critiques = self._collect_low_score_critiques(champion_runs)
            prelint = self.linter.lint(champion_md)  # feed champion's issues too
            candidate_md = self.rewriter.propose(
                champion_md, prelint, judge_critiques
            )
            rd.write_text(rd.candidate_path(i), candidate_md)

            # ---- gate 1: lint ----
            findings = self.linter.lint(candidate_md)
            rd.write_json(rd.lint_path(i), findings)
            lint_blocked = self.linter.has_blocking_findings(findings)

            if lint_blocked:
                log_(f"[caliper] round {i}: LINTER BLOCKED "
                     f"({sum(1 for f in findings if f.severity == Severity.HIGH)} HIGH findings)")
                report = RoundReport(
                    round_num=i,
                    candidate_md=candidate_md,
                    lint_findings=findings,
                    lint_blocked=True,
                    skill_runs_seed=champion_runs,
                    skill_runs_candidate=[],
                    seed_scores=champion_scores,
                    candidate_scores=[],
                    bootstrap_ci=None,
                    effect_size=None,
                    cs_ci=None,
                    decision=Decision(
                        accept=False,
                        reason=f"Linter blocked: {sum(1 for f in findings if f.severity == Severity.HIGH)} HIGH findings",
                        evidence={"findings": [f.kind for f in findings]},
                    ),
                )
                rd.write_json(rd.verdict_path(i), report.summary())
                reports.append(report)
                continue  # champion holds

            # ---- gate 2: judge panel ----
            log_(f"[caliper] round {i}: evaluating candidate on {len(eval_cases)} cases...")
            cand_runs = self._eval_skill(candidate_md, eval_cases)
            cand_scores = [self._run_score(r) for r in cand_runs]
            log_(f"[caliper] round {i}: candidate mean = {np.mean(cand_scores):.3f}, "
                 f"champion mean = {np.mean(champion_scores):.3f}")

            rd.write_skill_runs(i, cand_runs)

            # ---- Lagrangian length penalty (informational for now) ----
            body = candidate_md
            if "---\n" in body:
                # strip frontmatter for body length
                try:
                    body = body.split("---\n", 2)[2]
                except IndexError:
                    pass
            length_penalty = self._lagrangian.penalty(len(body))
            # update dual ascent (pulls lambda up if candidates keep overrunning)
            self._lagrangian.update(len(body))
            if length_penalty > 0:
                log_(f"[caliper] round {i}: body {len(body)} chars, "
                     f"lagrangian penalty={length_penalty:.4f}")

            # ---- gate 3 & 4: bootstrap + CS ----
            cmp_ = PairedComparison(
                seed=np.array(champion_scores), challenger=np.array(cand_scores)
            )
            ci = paired_bca_bootstrap(
                cmp_,
                n_resamples=self.config.bootstrap_n_resamples,
                alpha=self.config.bootstrap_alpha,
                seed=42 + i,
            )
            es = hedges_g(cmp_)
            pdcs.update_pairs(champion_scores, cand_scores)
            cs_ci = pdcs.ci_diff()

            # ---- decision ----
            accept, reason, evidence = self._decide(ci, cs_ci, es)
            decision = Decision(accept=accept, reason=reason, evidence=evidence)

            report = RoundReport(
                round_num=i,
                candidate_md=candidate_md,
                lint_findings=findings,
                lint_blocked=False,
                skill_runs_seed=champion_runs,
                skill_runs_candidate=cand_runs,
                seed_scores=champion_scores,
                candidate_scores=cand_scores,
                bootstrap_ci=ci,
                effect_size=es,
                cs_ci=cs_ci,
                decision=decision,
            )
            rd.write_json(rd.verdict_path(i), report.summary())
            reports.append(report)

            if accept:
                log_(f"[caliper] round {i}: ACCEPT — {reason}")
                champion_md = candidate_md
                champion_scores = cand_scores
                champion_runs = cand_runs
                rd.write_text(rd.champion_path, champion_md)
                # reset CS: new champion means new baseline
                pdcs = PairedDiffCS(alpha=self.config.cs_alpha)
            else:
                log_(f"[caliper] round {i}: REJECT — {reason}")

        # ---- final ----
        from caliper.persistence import _stable_hash  # type: ignore
        final = OptimizerResult(
            champion_md=champion_md,
            champion_hash=_stable_hash(champion_md),
            rounds=reports,
            final_decision=Decision(
                accept=(champion_md != seed_md),
                reason=(
                    "champion replaced by validated challenger"
                    if champion_md != seed_md
                    else "no challenger passed all gates; seed retained"
                ),
                evidence={"rounds_run": len(reports)},
            ),
        )
        rd.write_json(rd.final_path, {
            "champion_hash": final.champion_hash,
            "champion_replaced": champion_md != seed_md,
            "rounds": [r.summary() for r in reports],
            "budget": self._budget.snapshot(self._all_llms()),
            "llm_usage": {
                "target": self.target_lm.usage_snapshot(),
                "judges": self.judges.usage_summary(),
            },
            "cache_hit_size": len(self.judges._cache),
        })
        log_(f"[caliper] done. champion hash = {final.champion_hash}, "
             f"replaced = {champion_md != seed_md}")
        return final

    # ---- gates ----

    def _decide(
        self, ci: CIResult, cs_ci: CIResult, es: EffectSize,
    ) -> tuple[bool, str, dict]:
        """Accept ⇔ BCa CI excludes 0 AND CS lower bound > margin."""
        evidence = dict(
            bca_ci=(ci.ci_lower, ci.ci_upper),
            cs_ci=(cs_ci.ci_lower, cs_ci.ci_upper),
            hedges_g=es.hedges_g,
        )
        if not ci.significant_at_zero or ci.ci_lower <= 0:
            return False, f"BCa CI does not exclude 0: [{ci.ci_lower:+.3f}, {ci.ci_upper:+.3f}]", evidence
        if cs_ci.ci_lower <= self.config.cs_margin:
            return False, f"CS lower bound {cs_ci.ci_lower:+.3f} ≤ margin {self.config.cs_margin}", evidence
        return True, (
            f"BCa CI [{ci.ci_lower:+.3f}, {ci.ci_upper:+.3f}] & "
            f"CS lower {cs_ci.ci_lower:+.3f} > margin {self.config.cs_margin}"
        ), evidence

    # ---- eval loop ----

    def _eval_skill(
        self, skill_md: str, eval_cases: list[EvalCase]
    ) -> list[SkillRun]:
        runs: list[SkillRun] = []
        for case in eval_cases:
            response = self.target_lm.chat([
                ChatMessage(role="system", content=skill_md),
                ChatMessage(role="user", content=case.input),
            ], temperature=0.3, max_tokens=1024)

            verdict: JudgeVerdict = self.judges.score(
                input=case.input,
                response=response,
                principle=case.principle,
                rubric=case.rubric,
            )

            run = make_skill_run(
                input_text=case.input, response=response, skill_md=skill_md,
                id_seed=case.id,
            )
            # fold judge votes into SkillRun
            from caliper.schemas import JudgeScore
            run.judges = [
                JudgeScore(
                    model_family=v.model_family,
                    model_id=v.model_id,
                    rubric_item_id=case.id,
                    score=v.score,
                    raw_feedback=v.feedback,
                )
                for v in verdict.per_vote
            ]
            run.meta = {
                "ensemble_mean": verdict.mean,
                "ensemble_std": verdict.std,
                "conservative_score": verdict.conservative_score,
                "saturated": verdict.saturated,
                "disagreement_flag": verdict.disagreement_flag,
                "krippendorff_alpha": verdict.krippendorff_alpha,
            }
            runs.append(run)
        return runs

    @staticmethod
    def _run_score(run: SkillRun) -> float:
        """Use conservative_score from meta if present, else mean of judges."""
        meta = run.meta or {}
        if "conservative_score" in meta:
            return float(meta["conservative_score"])
        if run.judges:
            return float(np.mean([j.score for j in run.judges]))
        return 0.0

    @staticmethod
    def _collect_low_score_critiques(
        runs: Iterable[SkillRun],
    ) -> list[tuple[float, str]]:
        """Pull (score, feedback) pairs across worst-performing cases."""
        out: list[tuple[float, str]] = []
        for r in runs:
            if not r.judges:
                continue
            agg = float(np.mean([j.score for j in r.judges]))
            # Use judge with lowest score's feedback for maximum signal
            worst = min(r.judges, key=lambda j: j.score)
            out.append((agg, worst.raw_feedback))
        return out
