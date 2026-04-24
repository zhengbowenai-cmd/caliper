<h1 align="center">Probe</h1>

<p align="center">
  <strong>Algorithmically-guaranteed skill self-iteration for Claude Code.</strong>
  <br/>
  Every junction in the iteration loop carries a mathematical probe —
  <br/>
  so the system can run without human supervision and still know what it's doing.
</p>

<p align="center">
  <a href="https://github.com/OWNER/probe/actions"><img src="https://img.shields.io/github/actions/workflow/status/OWNER/probe/ci.yml?branch=main&label=CI&style=flat-square" alt="CI"/></a>
  <a href="https://github.com/OWNER/probe/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License"/></a>
  <img src="https://img.shields.io/badge/python-3.12%20%7C%203.13-informational?style=flat-square" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/types-pyright-forestgreen?style=flat-square" alt="Pyright"/>
  <img src="https://img.shields.io/badge/lint-ruff-orange?style=flat-square" alt="Ruff"/>
</p>

---

## Why does Probe exist?

Two rounds of POC on the Claude Code skill-iteration loop uncovered three recurring failure modes:

1. **Val-set overfitting.** A `+17%` gain on the validation slice turned into `-7.9%` on held-out domains.
2. **LLM reflection is noise, not gradient.** Attribution accuracy < 10% (AgenTracer / MAST 2025).
3. **Internal rule conflicts.** GEPA produced a skill whose "Always include a checklist" rule silently overrode a "trivial exception" rule, tanking every simple task.

None of the existing gates caught any of these. Probe is the algorithmic armor that does.

---

## Design principles

Three axioms, not negotiable:

| # | Principle | Implication |
|---|-----------|-------------|
| 1 | **Gradients come from algorithms, not LLMs.** | Reflection is a writer, not an attributor. Use Counterfactual Replay + TMC-Shapley instead. |
| 2 | **Every decision carries mathematical validity.** | No point-estimate promotions. BCa bootstrap, Hedges' g, Hedged-Capital CS, all reported. |
| 3 | **External anchors are irreplaceable.** | No pure-algorithmic system escapes the self-proof trap. Probe integrates human-in-the-loop gates and real user signals. |

---

## Install

```bash
# with uv (recommended — fast, no system Python pollution)
uv tool install probe

# or from source
git clone https://github.com/OWNER/probe.git
cd probe
uv sync --dev
```

Runtime requires an OpenAI-compatible LLM API. Tested against Alibaba DashScope (Qwen), DeepSeek, OpenAI, and OpenRouter.

```bash
# .env
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

---

## Quick start

Four CLI commands, all with rich terminal output and JSON-persistent run directories:

```bash
# 1. Static lint — catches the POC H04 "always checklist + trivial exception" bug,
#    description length overrun, invalid YAML, rule conflicts. Multilingual (EN + 中文).
probe lint path/to/SKILL.md

# 2. Per-section attribution — Counterfactual ablation + TMC-Shapley.
#    Tells you which sections of your skill are actually pulling their weight.
probe analyze skill.md --eval cases.jsonl

# 3. Head-to-head — paired BCa bootstrap + Hedges' g + peek-safe CS + linter.
probe compare seed.md challenger.md --eval cases.jsonl --run-dir runs/x

# 4. Full optimization loop — propose → lint → eval → decide, with hard budget caps.
probe iterate seed.md --eval cases.jsonl --rounds 3 \
    --run-dir runs/my-run \
    --judge-models qwen3.6-plus,qwen-max,qwen-plus \
    --max-cost-cny 50 \
    --cs-margin 0.02
```

### Eval file format (`*.jsonl`)

```json
{"id": "case-01", "input": "user prompt here", "principle": "what's being tested", "rubric": "0-10 rubric for the LLM judge"}
```

### Run directory layout

```
runs/my-run/
  config.json               frozen OptimizerConfig
  seed_skill.md             starting SKILL.md
  champion.md               current champion (updated on accept)
  rounds/
    round_000/
      candidate.md          LLM rewrite
      lint.json             LintFinding JSON
      skill_runs.jsonl      one SkillRun per eval case (with judge votes)
      verdict.json          BCa CI + Hedges g + CS CI + decision + reason
    round_001/ ...
  final.json                summary + budget + LLM usage + cache stats
```

---

## Architecture

Eight-layer design; the MVP ships four. See [`docs/architecture.md`](docs/architecture.md) for the full spec and [`docs/algorithms.md`](docs/algorithms.md) for references.

```
┌────────────────────────────────────────────────────────────────────┐
│ GROUND TRUTH     user signals · pairwise arena · external bench    │
│                       (V2 — external anchors)                      │
├────────────────────────────────────────────────────────────────────┤
│ STATISTICAL      BCa · Hedges' g · TOST · Hedged-Capital CS ·      │
│ SAFETY           Thresholdout · Track-and-Stop · BOCPD             │
├────────────────────────────────────────────────────────────────────┤
│ GRADIENT         Counterfactual Replay · TMC-Shapley · Oracle      │
│ SOURCE           Battery  (replaces LLM self-reflection)           │
├────────────────────────────────────────────────────────────────────┤
│ EVALUATOR        Ensemble judges · Krippendorff α · IRT · DML      │
├────────────────────────────────────────────────────────────────────┤
│ PROPOSER         LLM rewriter · Rule-Conflict Linter · Lagrangian  │
├────────────────────────────────────────────────────────────────────┤
│ ARCHIVE          MAP-Elites · Round-0 anchors · Pareto admission   │
├────────────────────────────────────────────────────────────────────┤
│ GOVERNANCE       Capability Manifest · Cost Budget · Privilege     │
├────────────────────────────────────────────────────────────────────┤
│ RUNTIME          Claude Code · Hermes skill-manager · Langfuse ·   │
│                  Inspect AI · GEPA (replaceable adapters)          │
└────────────────────────────────────────────────────────────────────┘
```

### Module map (what ships today)

| Path | What it does | Key refs |
|------|--------------|----------|
| `probe.safety.bootstrap` | Paired BCa bootstrap · Hedges' g · TOST (both t and bootstrap) · power | Efron 1987 · Hedges 1981 · Schuirmann 1987 |
| `probe.safety.confseq` | Hedged-Capital Confidence Sequence — peek-safe intervals | Waudby-Smith & Ramdas 2024 JRSSB |
| `probe.gradient.oracle` | Programmatic pass/fail checks | — |
| `probe.gradient.replay` | Counterfactual section ablation | Meng et al. 2022 (ROME) |
| `probe.gradient.shapley` | TMC Monte-Carlo Shapley over sections | Castro et al. 2009 · Ghorbani-Zou 2019 |
| `probe.evaluator.ensemble` | Multi-family ensemble · Krippendorff α · judge caching | Coste et al. 2024 ICLR · Krippendorff 2011 |
| `probe.proposer.linter` | Rule-Conflict Linter (EN + 中文) | POC-2 H04 |
| `probe.proposer.lagrangian` | Length constraint with dual ascent | Stooke et al. 2020 |
| `probe.proposer.rewriter` | LLM skill rewriter | — |
| `probe.governance.budget` | Token / wallclock / cost / rounds budget | — |
| `probe.runtime.llm` | OpenAI-compatible client with retry + token counting | — |
| `probe.optimizer` | Orchestrator wiring every gate | — |
| `probe.cli` | `probe lint / analyze / compare / iterate` | — |
| `probe.persistence` | JSON run-dir layout · SkillRun serialization | — |
| `probe.schemas` | `SkillRun`, `CIResult`, `Decision`, `EffectSize` | — |

---

## Demo: replay a known-bad decision

```bash
uv run python examples/karpathy-v2/demo.py
```

Running the demo against real POC-2 data produces:

```
1. BCa 95% CI on the "+17%" claim: [-0.175, +0.000]   → not significant at n=8
2. Required n for 80% power at d=0.3: ~88             → POC had n=8 (~15% power)
3. Peek-safe CS: wins? = False at every n ≤ 8         → promotion would have been blocked
4. Linter on best.md: 6 HIGH-severity findings, incl. the POC H04 pattern
```

Three independent gates, each sufficient to stop the wrong promotion.

---

## Contributing

We follow modern Python packaging and code-quality standards. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

- Formatter & linter: [`ruff`](https://docs.astral.sh/ruff/)
- Types: [`pyright`](https://github.com/microsoft/pyright) (strict standard mode)
- Tests: `pytest` (tests in `tests/`, fixtures in `conftest.py`)
- Pre-commit: `pre-commit install` then `pre-commit run --all-files`
- CI: GitHub Actions matrix (Python 3.12 · 3.13 on Ubuntu, macOS, Windows)

Run the full dev loop:

```bash
uv sync --dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest --cov=probe
```

---

## Security

If you discover a security vulnerability, please read [`SECURITY.md`](SECURITY.md) — do **not** open a public issue.

---

## Acknowledgements

- [anthropics/skills](https://github.com/anthropics/skills) — the SKILL.md format and `skill-creator` prior art
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) — `skill_manager_tool.py` design inspiration
- [gepa-ai/gepa](https://github.com/gepa-ai/gepa) — prompt-evolution baseline
- [UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai) — evaluation framework conventions

---

## License

MIT — see [`LICENSE`](LICENSE).
