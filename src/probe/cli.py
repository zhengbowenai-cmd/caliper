"""Probe CLI: lint | compare | iterate.

Examples
--------
    probe lint ~/.claude/skills/my-skill/SKILL.md

    probe compare seed.md challenger.md \
        --eval evals.jsonl \
        --run-dir runs/my-run

    probe iterate seed.md \
        --eval evals.jsonl \
        --rounds 3 \
        --run-dir runs/my-run
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from probe.evaluator.ensemble import EnsembleJudge
from probe.optimizer import (
    EvalCase,
    Optimizer,
    OptimizerConfig,
    load_eval_jsonl,
)
from probe.proposer.linter import LintFinding, RuleConflictLinter, Severity
from probe.proposer.rewriter import NaiveRewriter
from probe.runtime.llm import LLMClient

console = Console(legacy_windows=False, force_terminal=True, color_system="truecolor")


# ---------- helpers ----------


def _load_env(env_file: str | None) -> None:
    if env_file:
        load_dotenv(env_file)
    else:
        load_dotenv()  # local .env


def _build_qwen_ensemble(models: list[str]) -> EnsembleJudge:
    judges = [LLMClient.qwen(m) for m in models]
    return EnsembleJudge(judges=judges)


def _print_lint(findings: list[LintFinding], path: str) -> None:
    if not findings:
        console.print(Panel.fit(f"[green][OK] No findings[/green]\n{path}", box=box.ASCII))
        return
    table = Table(title=f"Lint findings: {path}", box=box.ASCII)
    table.add_column("#", justify="right", style="dim")
    table.add_column("severity")
    table.add_column("kind")
    table.add_column("message", overflow="fold")
    for i, f in enumerate(findings, 1):
        color = {"high": "red", "medium": "yellow", "low": "cyan"}.get(f.severity.value, "white")
        table.add_row(
            str(i),
            f"[{color}]{f.severity.value}[/{color}]",
            f.kind,
            f.message,
        )
    console.print(table)
    for i, f in enumerate(findings, 1):
        if f.evidence:
            console.print(f"[dim]  [{i}] evidence:[/dim]")
            for e in f.evidence[:3]:
                console.print(f"[dim]       · {e[:200]}[/dim]")


# ---------- commands ----------


@click.group()
def cli():
    """Probe: algorithmically-guaranteed skill self-iteration."""
    pass


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--eval", "eval_path", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="JSONL eval cases (used as scorer basis).")
@click.option("--env-file", default=None, type=click.Path())
@click.option("--target-model", default="qwen3.6-plus", show_default=True)
@click.option("--judge-models", default="qwen3.6-plus,qwen-max", show_default=True)
@click.option("--permutations", default=20, show_default=True,
              help="Number of Monte Carlo permutations for Shapley.")
@click.option("--skip-shapley", is_flag=True, default=False,
              help="Skip Shapley (faster — only CF ablation).")
def analyze(skill_path, eval_path, env_file, target_model, judge_models,
            permutations, skip_shapley):
    """Compute per-section attribution: CF ablation + TMC-Shapley.

    Tells you which sections of your SKILL.md are helping vs hurting,
    so you can edit by hand OR feed to an informed rewriter.
    """
    _load_env(env_file)
    if not os.getenv("DASHSCOPE_API_KEY"):
        console.print("[red]DASHSCOPE_API_KEY not set (check .env).[/red]")
        sys.exit(1)

    from probe.gradient import counterfactual_ablation, split_skill_sections, tmc_shapley

    md = Path(skill_path).read_text(encoding="utf-8")
    cases = load_eval_jsonl(eval_path)
    console.print(f"[cyan]Loaded {len(cases)} eval cases; analyzing '{skill_path}'[/cyan]")

    target = LLMClient.qwen(target_model)
    judges = _build_qwen_ensemble([m.strip() for m in judge_models.split(",")])

    # build a scorer(skill_md) -> float that evaluates on all eval cases
    import numpy as np
    from probe.runtime.llm import ChatMessage

    def scorer(skill_md_variant: str) -> float:
        scores = []
        for c in cases:
            resp = target.chat(
                [ChatMessage(role="system", content=skill_md_variant),
                 ChatMessage(role="user", content=c.input)],
                temperature=0.3, max_tokens=1024,
            )
            verdict = judges.score(input=c.input, response=resp,
                                   principle=c.principle, rubric=c.rubric)
            scores.append(verdict.conservative_score)
        return float(np.mean(scores))

    split = split_skill_sections(md)
    if not split.sections:
        console.print("[yellow]No top-level sections (# / ## / ###) found — nothing to ablate.[/yellow]")
        sys.exit(0)

    console.print(f"[cyan]Found {len(split.sections)} sections. "
                  f"Computing baseline score...[/cyan]")
    baseline = scorer(md)
    console.print(f"[cyan]Baseline score = {baseline:.3f}[/cyan]")

    console.print(f"[cyan]Running CF ablation (N={len(split.sections)} evals)...[/cyan]")
    ace = counterfactual_ablation(md, scorer, baseline_score=baseline)

    t = Table(title="Counterfactual Ablation (positive = section helps)",
              box=box.ASCII)
    t.add_column("section")
    t.add_column("ACE", justify="right")
    t.add_column("chars", justify="right")
    for (h, b) in split.sections:
        delta = ace[h.strip()]
        color = "green" if delta > 0.02 else ("red" if delta < -0.02 else "white")
        t.add_row(h, f"[{color}]{delta:+.3f}[/]", str(len(b)))
    console.print(t)

    if not skip_shapley:
        console.print(f"[cyan]Running TMC-Shapley with {permutations} permutations "
                      f"(will cache subsets to save cost)...[/cyan]")
        phi = tmc_shapley(md, scorer, num_permutations=permutations, seed=42)

        t2 = Table(title="TMC-Shapley attribution (sum ≈ baseline - empty)",
                   box=box.ASCII)
        t2.add_column("section")
        t2.add_column("phi_i", justify="right")
        for (h, _) in split.sections:
            v = phi[h.strip()]
            color = "green" if v > 0.02 else ("red" if v < -0.02 else "white")
            t2.add_row(h, f"[{color}]{v:+.3f}[/]")
        console.print(t2)
        console.print(f"[dim]sum(phi) = {sum(phi.values()):+.3f}[/dim]")

    console.print(f"\n[bold]Token usage:[/bold] "
                  f"target={target.total_prompt_tokens + target.total_completion_tokens:,}  "
                  f"judges={judges.usage_summary()['total']['prompt_tokens'] + judges.usage_summary()['total']['completion_tokens']:,}")


@cli.command()
@click.argument("skill_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--desc-limit", default=1024, show_default=True,
              help="Max chars for description frontmatter field.")
@click.option("--body-limit", default=6000, show_default=True,
              help="Soft cap on body length.")
def lint(skill_path: str, desc_limit: int, body_limit: int):
    """Run the Rule Conflict Linter on a SKILL.md.

    Exit code 0 if no HIGH findings, 2 if HIGH findings present.
    """
    md = Path(skill_path).read_text(encoding="utf-8")
    linter = RuleConflictLinter(description_char_limit=desc_limit, body_char_limit=body_limit)
    findings = linter.lint(md)
    _print_lint(findings, skill_path)
    if linter.has_blocking_findings(findings):
        sys.exit(2)


@cli.command()
@click.argument("seed_path", type=click.Path(exists=True, dir_okay=False))
@click.argument("challenger_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--eval", "eval_path", required=True,
              type=click.Path(exists=True, dir_okay=False),
              help="JSONL file of test cases (id/input/principle/rubric).")
@click.option("--run-dir", required=True, type=click.Path(),
              help="Directory to persist SkillRun artifacts.")
@click.option("--env-file", default=None, type=click.Path(),
              help="Optional .env file; defaults to local ./.env")
@click.option("--target-model", default="qwen3.6-plus", show_default=True)
@click.option("--judge-models", default="qwen3.6-plus,qwen-max,qwen-plus",
              show_default=True,
              help="Comma-sep list of judge models (DashScope / Qwen).")
def compare(seed_path, challenger_path, eval_path, run_dir,
            env_file, target_model, judge_models):
    """Head-to-head: score seed vs challenger with full statistical report."""
    _load_env(env_file)
    if not os.getenv("DASHSCOPE_API_KEY"):
        console.print("[red]DASHSCOPE_API_KEY not set (check .env).[/red]")
        sys.exit(1)

    seed_md = Path(seed_path).read_text(encoding="utf-8")
    chal_md = Path(challenger_path).read_text(encoding="utf-8")
    cases = load_eval_jsonl(eval_path)
    console.print(f"[cyan]Loaded {len(cases)} eval cases.[/cyan]")

    target = LLMClient.qwen(target_model)
    judges = _build_qwen_ensemble([m.strip() for m in judge_models.split(",")])
    rewriter = NaiveRewriter(llm=target)   # unused in compare but Optimizer needs one
    linter = RuleConflictLinter()

    # We use Optimizer but skip proposing: manually evaluate both skills.
    opt = Optimizer(
        target_lm=target, judges=judges, rewriter=rewriter, linter=linter,
        config=OptimizerConfig(max_rounds=0),
    )

    from probe.persistence import RunDir
    rd = RunDir(run_dir)
    rd.write_text(rd.seed_path, seed_md)

    console.print(f"[cyan]Evaluating seed...[/cyan]")
    seed_runs = opt._eval_skill(seed_md, cases)
    console.print(f"[cyan]Evaluating challenger...[/cyan]")
    chal_runs = opt._eval_skill(chal_md, cases)

    seed_scores = [opt._run_score(r) for r in seed_runs]
    chal_scores = [opt._run_score(r) for r in chal_runs]

    # Lint both sides
    seed_lint = linter.lint(seed_md)
    chal_lint = linter.lint(chal_md)

    # Stats
    import numpy as np
    from probe.safety import PairedComparison, paired_bca_bootstrap, hedges_g
    from probe.safety.confseq import PairedDiffCS

    cmp_ = PairedComparison(seed=np.array(seed_scores), challenger=np.array(chal_scores))
    ci = paired_bca_bootstrap(cmp_, n_resamples=5000, seed=42)
    es = hedges_g(cmp_)
    pdcs = PairedDiffCS(alpha=0.05)
    pdcs.update_pairs(seed_scores, chal_scores)
    cs_ci = pdcs.ci_diff()

    # Per-case table
    t = Table(title="per-case", box=box.ASCII)
    t.add_column("id")
    t.add_column("seed", justify="right")
    t.add_column("chal", justify="right")
    t.add_column("diff", justify="right")
    for c, s, ch in zip(cases, seed_scores, chal_scores):
        d = ch - s
        mark = "^" if d > 0.05 else ("v" if d < -0.05 else "=")
        t.add_row(c.id, f"{s:.2f}", f"{ch:.2f}", f"[{'green' if d>0 else ('red' if d<0 else 'white')}]{d:+.2f}[/] {mark}")
    console.print(t)

    verdict = Table(title="statistical verdict", box=box.ASCII, show_header=False)
    verdict.add_column("metric", style="bold cyan")
    verdict.add_column("value")
    verdict.add_row("n", str(cmp_.n))
    verdict.add_row("seed mean", f"{np.mean(seed_scores):.3f}")
    verdict.add_row("challenger mean", f"{np.mean(chal_scores):.3f}")
    verdict.add_row("mean diff", f"{cmp_.mean_diff:+.3f}")
    verdict.add_row("BCa 95% CI", f"[{ci.ci_lower:+.3f}, {ci.ci_upper:+.3f}]")
    verdict.add_row("BCa sig at 0?",
                    "[green]YES[/green]" if ci.significant_at_zero else "[red]NO[/red]")
    verdict.add_row("Hedges' g", f"{es.hedges_g:+.3f} ({es.interpretation})")
    verdict.add_row("CS diff CI", f"[{cs_ci.ci_lower:+.3f}, {cs_ci.ci_upper:+.3f}]")
    verdict.add_row("linter seed HIGH", str(sum(1 for f in seed_lint if f.severity == Severity.HIGH)))
    verdict.add_row("linter chal HIGH",
                    f"{sum(1 for f in chal_lint if f.severity == Severity.HIGH)}"
                    + ("  [red](BLOCK)[/red]" if linter.has_blocking_findings(chal_lint) else ""))
    console.print(verdict)

    # Persist
    payload = {
        "seed_scores": seed_scores,
        "challenger_scores": chal_scores,
        "bca_ci": ci.model_dump(),
        "hedges_g": es.hedges_g,
        "cs_ci": cs_ci.model_dump(),
        "seed_lint_high": sum(1 for f in seed_lint if f.severity == Severity.HIGH),
        "chal_lint_high": sum(1 for f in chal_lint if f.severity == Severity.HIGH),
    }
    (rd.root / "compare.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    console.print(f"[dim]Saved to {rd.root}/compare.json[/dim]")


@cli.command()
@click.argument("seed_path", type=click.Path(exists=True, dir_okay=False))
@click.option("--eval", "eval_path", required=True,
              type=click.Path(exists=True, dir_okay=False))
@click.option("--rounds", default=3, show_default=True,
              help="Max proposal rounds.")
@click.option("--run-dir", required=True, type=click.Path())
@click.option("--env-file", default=None, type=click.Path())
@click.option("--target-model", default="qwen3.6-plus", show_default=True)
@click.option("--judge-models", default="qwen3.6-plus,qwen-max,qwen-plus",
              show_default=True)
@click.option("--cs-margin", default=0.02, show_default=True, type=float,
              help="CS lower bound on diff must exceed this to promote.")
@click.option("--max-wallclock-s", default=None, type=float,
              help="Hard wallclock budget in seconds. None = unlimited.")
@click.option("--max-tokens", default=None, type=int,
              help="Hard total-token budget. None = unlimited.")
@click.option("--max-cost-cny", default=None, type=float,
              help="Hard CNY budget based on family rate tables. None = unlimited.")
@click.option("--resume", is_flag=True, default=False,
              help="Resume run_dir: use existing champion.md as new seed, "
                   "skipping completed rounds.")
def iterate(seed_path, eval_path, rounds, run_dir, env_file,
            target_model, judge_models, cs_margin,
            max_wallclock_s, max_tokens, max_cost_cny, resume):
    """Run the full propose → lint → eval → decide loop."""
    _load_env(env_file)
    if not os.getenv("DASHSCOPE_API_KEY"):
        console.print("[red]DASHSCOPE_API_KEY not set (check .env).[/red]")
        sys.exit(1)

    seed_md = Path(seed_path).read_text(encoding="utf-8")
    cases = load_eval_jsonl(eval_path)

    target = LLMClient.qwen(target_model)
    judges = _build_qwen_ensemble([m.strip() for m in judge_models.split(",")])
    rewriter = NaiveRewriter(llm=target)
    linter = RuleConflictLinter()

    cfg = OptimizerConfig(
        max_rounds=rounds,
        cs_margin=cs_margin,
        max_wallclock_s=max_wallclock_s,
        max_tokens=max_tokens,
        max_cost_cny=max_cost_cny,
    )
    opt = Optimizer(
        target_lm=target, judges=judges, rewriter=rewriter,
        linter=linter, config=cfg,
    )

    def say(msg: str) -> None:
        console.print(msg)

    result = opt.run(seed_md, cases, run_dir=run_dir, progress=say, resume=resume)

    console.rule("[bold]final[/bold]")
    summary = Table(box=box.ASCII)
    summary.add_column("round")
    summary.add_column("lint")
    summary.add_column("seed μ")
    summary.add_column("cand μ")
    summary.add_column("CI")
    summary.add_column("g")
    summary.add_column("decision")
    for r in result.rounds:
        s = r.summary()
        summary.add_row(
            str(s["round"]),
            f"{s['lint_high']}H" + (" BLOCK" if r.lint_blocked else ""),
            f"{s['seed_mean']:.2f}" if s["seed_mean"] is not None else "-",
            f"{s['cand_mean']:.2f}" if s["cand_mean"] is not None else "-",
            (f"[{s['ci']['ci_lower']:+.2f},{s['ci']['ci_upper']:+.2f}]"
             if s["ci"] else "-"),
            f"{s['hedges_g']:+.2f}" if s["hedges_g"] is not None else "-",
            "[green]PASS[/green]" if s["accept"] else f"[red]FAIL[/red] {s['reason'][:40]}",
        )
    console.print(summary)

    console.print(
        f"\n[bold]{'Champion REPLACED' if result.champion_md != seed_md else 'Seed RETAINED'}[/bold]"
        f"  (hash={result.champion_hash})"
    )


if __name__ == "__main__":
    cli()
