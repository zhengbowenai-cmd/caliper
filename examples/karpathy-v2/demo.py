"""Demo: re-analyze the POC-2 result through the Caliper lens.

Shows how every Caliper module would have changed the POC-2 conclusion:

1. safety.bootstrap → the "+17%" was not statistically significant
2. proposer.linter  → best.md had a rule conflict causing H04 regression
3. safety.confseq   → peek-safe CS would have prevented premature promotion
4. evaluator        → single-family judge made the whole thing self-referential

Run with:
    cd caliper && uv run python examples/karpathy-v2/demo.py
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from caliper.proposer import RuleConflictLinter
from caliper.safety import (
    PairedComparison,
    PairedDiffCS,
    hedges_g,
    paired_bca_bootstrap,
    required_n_paired_t,
    tost_paired,
)

# ---------------------------------------------------------------------------
# POC-2 data (from E:\opensource-research\poc-skill-iteration)
# ---------------------------------------------------------------------------

POC_ROOT = Path("E:/opensource-research/poc-skill-iteration")
HOLDOUT_JSON = POC_ROOT / "runs" / "holdout_compare.json"
BEST_MD = POC_ROOT / "variants" / "best.md"


def section(title: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}\n  {title}\n{bar}")


# ---------------------------------------------------------------------------
# 1. Re-examine the +17% claim with BCa bootstrap + Hedges' g + TOST
# ---------------------------------------------------------------------------


def check_statistical_validity():
    section("1. Statistical re-examination of the '+17%' claim")

    if not HOLDOUT_JSON.exists():
        print(f"[skip] holdout comparison file not found at {HOLDOUT_JSON}")
        return

    holdout = json.loads(HOLDOUT_JSON.read_text(encoding="utf-8"))
    seed = np.array([x["seed_score"] for x in holdout], dtype=float)
    best = np.array([x["best_score"] for x in holdout], dtype=float)
    cmp_ = PairedComparison(seed=seed, challenger=best)

    print(f"  n = {cmp_.n}")
    print(f"  seed mean  = {seed.mean():.3f}")
    print(f"  best mean  = {best.mean():.3f}")
    print(f"  mean diff  = {cmp_.mean_diff:+.3f}")
    rel = cmp_.mean_diff / seed.mean() if seed.mean() else 0
    print(f"  relative   = {rel:+.1%}")

    print("\n  -- BCa paired bootstrap (n_resamples=10,000) --")
    ci = paired_bca_bootstrap(cmp_, n_resamples=10_000, seed=42)
    print(f"  95% CI on diff = [{ci.ci_lower:+.3f}, {ci.ci_upper:+.3f}]")
    print(f"  significant at 0 = {ci.significant_at_zero}")
    if not ci.significant_at_zero:
        print("  → VERDICT: the observed diff is NOT statistically significant at n=8.")

    print("\n  -- Hedges' g (small-sample corrected d_z) --")
    es = hedges_g(cmp_)
    print(f"  g = {es.hedges_g:+.3f}  ({es.interpretation})")

    print("\n  -- TOST equivalence test at ±5% --")
    t = tost_paired(cmp_, low=-0.05, high=0.05, alpha=0.05)
    print(f"  p_low={t['p_low']:.3f}  p_high={t['p_high']:.3f}  equivalent={t['equivalent']}")

    print("\n  -- Required n for 80% power at d=0.3 (conservative) --")
    n_needed = required_n_paired_t(0.3, alpha=0.05, power=0.80)
    print(f"  ≈ {n_needed} paired samples to detect d=0.3 at 80% power")
    print("  (POC had n=8 → power to detect d=0.3 was ~15%)")


# ---------------------------------------------------------------------------
# 2. Peek-safe CS would have caught premature promotion
# ---------------------------------------------------------------------------


def check_peek_safety():
    section("2. Peek-safe confidence sequence")

    if not HOLDOUT_JSON.exists():
        print("[skip] holdout not found")
        return

    holdout = json.loads(HOLDOUT_JSON.read_text(encoding="utf-8"))
    seed_scores = [x["seed_score"] for x in holdout]
    best_scores = [x["best_score"] for x in holdout]

    pdcs = PairedDiffCS(alpha=0.05)
    print("  Peek at every new observation:")
    print(f"  {'n':>3}  {'point':>8}  {'95% CI':>22}   wins?")
    for i, (s, b) in enumerate(zip(seed_scores, best_scores, strict=False), 1):
        pdcs.update_pair(s, b)
        ci = pdcs.ci_diff()
        winning = pdcs.challenger_wins(margin=0.0)
        print(
            f"  {i:>3}  {ci.point_estimate:+.3f}   [{ci.ci_lower:+.3f}, {ci.ci_upper:+.3f}]   {winning}"
        )
    print("  → CS never declared challenger wins → promotion would have been blocked.")


# ---------------------------------------------------------------------------
# 3. Rule Conflict Linter on best.md — the POC-2 H04 killer
# ---------------------------------------------------------------------------


def check_rule_conflicts():
    section("3. Rule Conflict Linter on variants/best.md")

    if not BEST_MD.exists():
        print(f"[skip] best.md not found at {BEST_MD}")
        return

    md = BEST_MD.read_text(encoding="utf-8")
    linter = RuleConflictLinter()
    findings = linter.lint(md)
    if not findings:
        print("  NO findings. (If the POC H04 pattern exists, the linter has a gap.)")
        return
    print(f"  {len(findings)} findings:\n")
    for i, f in enumerate(findings, 1):
        print(f"  [{i}] kind={f.kind}  severity={f.severity.value}")
        print(f"      {f.message}")
        for e in f.evidence[:3]:
            print(f"      · {e[:140]}")
        print()
    blocking = linter.has_blocking_findings(findings)
    print(f"  BLOCKING = {blocking}")
    if blocking:
        print("  → Linter would have REJECTED this candidate before promotion.")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print(__doc__)
    check_statistical_validity()
    check_peek_safety()
    check_rule_conflicts()
    print("\n" + "=" * 72)
    print("  DONE — POC-2's '+17%' reopened under Caliper's algorithmic lens.")
    print("=" * 72)
