<p align="right"><b>English</b> · <a href="README.zh-CN.md">简体中文</a></p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img alt="Caliper — Algorithmically-guaranteed skill self-iteration" src="assets/banner.svg" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/zhengbowenai-cmd/caliper/actions"><img src="https://img.shields.io/github/actions/workflow/status/zhengbowenai-cmd/caliper/ci.yml?branch=master&label=CI&style=flat-square" alt="CI"/></a>
  <a href="https://github.com/zhengbowenai-cmd/caliper/blob/master/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License"/></a>
  <img src="https://img.shields.io/badge/python-3.12%20%7C%203.13-informational?style=flat-square" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/types-pyright-forestgreen?style=flat-square" alt="Pyright"/>
  <img src="https://img.shields.io/badge/lint-ruff-orange?style=flat-square" alt="Ruff"/>
</p>

<p align="center">
  <a href="docs/quickstart.md">Quickstart</a> ·
  <a href="docs/architecture.md">Architecture</a> ·
  <a href="docs/algorithms.md">Algorithms</a> ·
  <a href="CONTRIBUTING.md">Contributing</a> ·
  <a href="CHANGELOG.md">Changelog</a> ·
  <a href="SECURITY.md">Security</a>
</p>

---

## What is Caliper?

In one line: **you changed how the AI behaves — Caliper tells you whether the change actually helped.**

### A scenario you've probably been in

You're using Claude Code (or any LLM agent). It sometimes touches code it shouldn't, sometimes makes simple tasks complicated. So you wrote a behavior file (a `SKILL.md`) telling it how to behave better. Everyone does this.

After your edit, **how do you know your behavior file actually made it better?**

Eyeball a few outputs? Feels about the same? Or is it secretly worse and you can't tell?

We learned the hard way:

> A change scored **+17%** on the validation set. Felt great. Ready to ship.
> Re-ran on real-world cases — it scored **−8%**.
> The "improvement" was pure random noise — invisible to the eye.

### What Caliper does for you

One job: **take your old version vs your new version, run them through tests, and give a clear verdict — *ship it* or *don't*.**

Every verdict tells you:
- ✅ which test cases got better, ❌ which got worse
- whether the difference is real or just randomness
- **which paragraphs of your behavior file are helping, and which are dragging it down**

Unlike "review a few examples by eye," Caliper doesn't sleep, every conclusion is auditable, and every verdict comes with a number you can check.

### Four things it can do

| Command | What it does for you |
|---------|---------------------|
| 🔍 `caliper lint <file>` | **Static check on your behavior file** — catches the bug where *"Always include a checklist"* and *"skip ceremony for trivial tasks"* silently contradict each other. AI-written behavior files step on this trap constantly. **Works for English and Chinese.** |
| 📏 `caliper compare old.md new.md` | **Old version vs new, head to head** — tells you whether your "+17% improvement" is real or just looked good on a small sample |
| 🔄 `caliper iterate` | **Full automatic loop** — let the AI propose improvements → lint for conflicts → run tests → only accept if statistics pass. Hard cost ceiling means it **can't burn through your API budget** |
| 🔬 `caliper analyze` | **Section-level autopsy** — slices your behavior file paragraph by paragraph and tells you **which paragraphs help and which hurt** |

### Two guarantees that protect you

- **Free, fully open source forever** (MIT). Caliper itself charges you nothing.
- **Cannot overspend.** Your LLM provider charges per token — Caliper can't change that — but a built-in `--max-cost-cny 50`-style hard cap means it stops the moment you hit your budget. **No surprise 4 AM bills.**

---

## See it in action

```bash
$ caliper compare seed.md challenger.md --eval my_cases.jsonl
```
```
                        per-case
+----------------------------+------+------+---------+
| id                         | seed | chal |    diff |
+----------------------------+------+------+---------+
| 01-ambiguity-cache         | 1.00 | 1.00 |   +0.00 |
| 02-over-engineering-config | 1.00 | 1.00 |   +0.00 |
| 03-defensive-sum           | 1.00 | 1.00 |   +0.00 |
| 04-surgical-bug            | 0.80 | 0.95 |   +0.15 |
| 05-trivial-rename          | 0.90 | 0.40 |   −0.50 |  ← regression!
| 06-pushback-singleton      | 1.00 | 1.00 |   +0.00 |
| 07-trivial-typo            | 0.90 | 0.30 |   −0.60 |  ← regression!
| 08-verifiable-perf         | 1.00 | 1.00 |   +0.00 |
+----------------------------+------+------+---------+

                statistical verdict
+----------------+------------------------------+
| n              | 8                            |
| seed mean      | 0.825                        |
| challenger     | 0.700                        |
| mean diff      | −0.125                       |
| 95% BCa CI     | [−0.275, +0.000]             |
| Hedges' g      | −0.42  (small)               |
| linter (chal)  | 6 HIGH findings  (BLOCK)     |
+----------------+------------------------------+

→ DO NOT PROMOTE
   - linter found a rule conflict ("Always checklist" + "Trivial Exception")
   - statistical CI does not exclude zero on 8 samples
```

You wouldn't have shipped this. Caliper made the call before you even rolled it out.

---

## Install

```bash
# Prerequisite: uv (https://docs.astral.sh/uv/)
git clone https://github.com/zhengbowenai-cmd/caliper.git
cd caliper
uv sync --dev
```

Caliper talks to any **OpenAI-compatible LLM** — DashScope (Qwen), DeepSeek, OpenAI, OpenRouter, local vLLM, all work. Set one in `.env`:

```bash
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

> **Free, fully open source (MIT).** Caliper itself never charges you anything. The only money involved is what you pay your LLM provider for inference — and Caliper has a hard `--max-cost-cny` cap so you can't be surprised.

Full setup walkthrough: [`docs/quickstart.md`](docs/quickstart.md).

---

## Why does this matter?

Three failure modes show up over and over when people iterate on skills, and **none of the existing tools catch them**:

1. **Validation overfitting.** A `+17%` gain on val turned into `-7.9%` on holdout in our POC. Without a confidence interval you'd never have noticed.
2. **LLM reflection is noise.** When you ask an LLM "what went wrong?", attribution accuracy is under 10% (AgenTracer / MAST 2025). Most "improvements" guided by reflection are random walks.
3. **Internal rule conflicts.** A skill saying *"always include a checklist"* AND *"skip ceremony for trivial tasks"* — both rules can't be right. The "always" wins, and trivial tasks get crushed.

Caliper is the algorithmic armor that closes all three. It doesn't trust point estimates, doesn't trust LLM self-attribution, and doesn't trust rules that contradict each other.

---

## Design principles

| # | Principle | Why |
|---|-----------|-----|
| 1 | **Gradients come from algorithms, not LLMs.** | Reflection is a writer, not an attributor. We use Counterfactual Replay + TMC-Shapley instead. |
| 2 | **Every decision carries mathematical validity.** | No point-estimate promotions. BCa bootstrap, Hedges' g, Hedged-Capital CS — every verdict has a number you can audit. |
| 3 | **External anchors are irreplaceable.** | No purely automated system escapes the self-proof trap. Caliper surfaces — never bypasses — human sign-off. |

---

## Architecture (for the curious)

Caliper is eight layers stacked into one CLI. The MVP ships five.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/architecture-dark.svg">
    <img alt="Caliper architecture — eight layers" src="assets/architecture.svg" width="100%">
  </picture>
</p>

Each layer's algorithm cites a peer-reviewed source. See [`docs/algorithms.md`](docs/algorithms.md) for every reference, [`docs/architecture.md`](docs/architecture.md) for the full spec.

---

## What's not in scope

- Fine-tuning model weights. Caliper operates on **skill text only**.
- Replacing your LLM. Bring any OpenAI-compatible endpoint.
- Telling you what to write. Caliper measures; you decide.

---

## Demo: replay a known-bad decision on real data

```bash
uv run python examples/karpathy-v2/demo.py
```

Real POC-2 data, four lines of verdict:

```
1. BCa 95% CI on the "+17%" claim:    [-0.175, +0.000]    →  not significant at n=8
2. Required n for 80% power at d=0.3: ~88                 →  POC had n=8 (~15% power)
3. Peek-safe CS: "wins?" = False at every n ≤ 8           →  promotion would have been blocked
4. Linter on best.md:  6 HIGH findings, incl. POC-2 H04 pattern
```

Three independent gates, each sufficient to reverse the wrong promotion.

---

## Contributing

We follow modern Python standards. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

`ruff` (format + lint) · `pyright` (types) · `pytest` (46/46 passing) · `pre-commit` · `gitleaks` · CodeQL · CI matrix on Python 3.12 / 3.13 × Ubuntu / macOS / Windows.

---

## Acknowledgements

- [`anthropics/skills`](https://github.com/anthropics/skills) — SKILL.md format and `skill-creator` prior art
- [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent) — `skill_manager_tool.py` design inspiration
- [`gepa-ai/gepa`](https://github.com/gepa-ai/gepa) — prompt-evolution baseline
- [`UKGovernmentBEIS/inspect_ai`](https://github.com/UKGovernmentBEIS/inspect_ai) — evaluation framework conventions

---

## License

MIT — fully free, forever. See [`LICENSE`](LICENSE).
