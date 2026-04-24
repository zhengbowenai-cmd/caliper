# Caliper Architecture

> This document describes the full V1 architecture. The MVP ships the
> **Statistical Safety**, **Gradient Source**, **Proposer**, **Evaluator**,
> and **Governance** layers. Everything below prefixed *V2* is planned.

## Design axioms

1. **Gradients come from algorithms, not LLMs.** Reflection attribution
   is empirically noisy (< 10 % accuracy on complex traces — AgenTracer,
   MAST). Caliper replaces "ask an LLM what went wrong" with
   Counterfactual Replay + TMC-Shapley.
2. **Every decision carries mathematical validity.** A point estimate
   never promotes a candidate by itself; only a paired BCa bootstrap
   whose CI excludes zero, combined with a Confidence Sequence that
   exceeds a pre-registered margin, can.
3. **External anchors are irreplaceable.** No algorithmic defense
   escapes the self-proof trap forever — real user signals and
   human-in-the-loop gates are required for safety-critical promotions.

## Eight layers

```
┌────────────────────────────────────────────────────────────────────┐
│ GROUND TRUTH          user signals · pairwise arena · ext bench    │ V2
├────────────────────────────────────────────────────────────────────┤
│ STATISTICAL SAFETY    Thresholdout · Hedged-Cap CS · BCa · TOST ·  │
│                       Hedges · BOCPD (drift) · Track-and-Stop BAI  │
├────────────────────────────────────────────────────────────────────┤
│ GRADIENT SOURCE       Counterfactual Replay · TMC-Shapley · Oracle │
│                       Battery (replaces LLM self-reflection)       │
├────────────────────────────────────────────────────────────────────┤
│ EVALUATOR             Ensemble · Krippendorff α · IRT-GRM ·        │
│                       DML · Causal Forest · meta-judge recert      │
├────────────────────────────────────────────────────────────────────┤
│ PROPOSER              LLM rewriter · Rule-Conflict Linter ·        │
│                       Lagrangian length                            │
├────────────────────────────────────────────────────────────────────┤
│ ARCHIVE               MAP-Elites · Pareto admission · Round-0      │ V2
│                       anchors (immutable)                          │
├────────────────────────────────────────────────────────────────────┤
│ GOVERNANCE            Capability Manifest · Cost Budget ·          │
│                       Privilege Envelope · Human Sign Gate         │
├────────────────────────────────────────────────────────────────────┤
│ RUNTIME               Claude Code · Hermes skill-manager ·         │
│                       Langfuse · Inspect AI · GEPA (adapters)      │
└────────────────────────────────────────────────────────────────────┘
```

## One optimization round

```
propose ─▶ lint ─▶ judge-panel eval ─▶ bootstrap CI ─▶ CS update ─▶ decide
   ▲         │          │                    │              │          │
   │         └──HIGH:REJECT                  │              │          │
   │                    │           not sig ─┤        below ─┤         │
   └────────── reject ◄─┴────────────────────┴──────────────┘          │
                                                                       ▼
                                                       ACCEPT: champion ← candidate
```

Every rejection is *recorded with reason* in `verdict.json`. No silent drops.

## Gate chain — rejection reasons

| Gate | Library | Raise when | Typical cause |
|------|---------|------------|---------------|
| Linter | `caliper.proposer.linter` | any HIGH finding | rule conflict, frontmatter overrun |
| Judge panel | `caliper.evaluator.ensemble` | all judges `parse_error` | rubric misaligned, LLM refusal |
| Bootstrap CI | `caliper.safety.bootstrap` | CI straddles 0 | small n, noisy metric |
| CS | `caliper.safety.confseq` | lower bound ≤ margin | insufficient evidence under sequential peek |
| Budget | `caliper.governance.budget` | wallclock / tokens / yuan / rounds exceeded | — |

## Data contract — `SkillRun`

Every component reads and writes the same schema. See
[`src/caliper/schemas.py`](../src/caliper/schemas.py).

```python
class SkillRun(BaseModel):
    id: str
    skill_version_hash: str
    input: str
    response: str
    trace: list[TraceStep]
    oracle: OracleResult | None       # authoritative when present
    judges: list[JudgeScore]          # multi-family
    theta_irt: float | None           # V2 — IRT-GRM latent ability
    user_signal: UserSignal | None    # V2 — Claude Code hooks
    shapley: dict[str, float]         # section_id -> phi_i
    cf_diff: dict[str, str]
    meta: dict[str, Any]
```

Persistence: one JSON line per SkillRun under
`runs/<run>/rounds/round_NNN/skill_runs.jsonl`. Plain files; external
tooling (jq, DuckDB) can query them directly.

## What is *not* in scope

- Fine-tuning model weights. Caliper operates on skill text only.
- Running arbitrary user tools. Skills are assumed to go through Claude
  Code's own tool-use; Caliper just writes the SKILL.md.
- Replacing the LLM. Caliper is provider-agnostic; bring your own
  OpenAI-compatible endpoint.

## Replaceable adapters

Every external system is an adapter behind a Caliper interface. Swapping
any of these does not touch the gate chain:

| Caliper interface | Adapter today | Swappable with |
|-----------------|---------------|----------------|
| `LLMClient` | OpenAI SDK + `api_base` override | Anthropic Messages SDK, vLLM, local |
| `ensemble.EnsembleJudge` | per-case parallel call | Inspect AI Scorer |
| Skill CRUD | — (V1) | Hermes `skill_manager_tool.py` |
| Trace sink | JSONL | Langfuse |
| Proposer | `NaiveRewriter` | GEPA `optimize_anything`, DSPy `GEPA` |

## References

See [`docs/algorithms.md`](algorithms.md).
