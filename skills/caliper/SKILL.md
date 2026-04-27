---
name: caliper
description: |
  Statistically test whether a prompt or SKILL.md change is actually
  better than the old version. Use when the user asks to compare two
  prompts, A/B test a prompt change, check if a recent edit really
  improved things, find rule conflicts in a long prompt, or identify
  which sections of a prompt are pulling weight. Multilingual (EN +
  中文). Replaces "I think it's better" with a confidence interval.
license: MIT
homepage: https://github.com/zhengbowenai-cmd/caliper
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
---

# Caliper — Statistical A/B testing for AI prompts and skills

Use this skill when the user wants to **objectively know whether a new
prompt is better than the old one** — instead of eyeballing a few
outputs and guessing.

## When to invoke this skill

Trigger phrases that should activate Caliper:

- "Is this prompt actually better than the old one?"
- "A/B test these two SKILL.md files"
- "Did my prompt edit really improve things?"
- "Which paragraph of this prompt is dragging it down?"
- "Lint this prompt for contradictions"
- "Compare seed.md and challenger.md"
- 中文：「新版 prompt 真的比旧版好吗」「测一下这次改动有没有用」「找出 prompt 里互相打架的规则」「这一段在拉分还是扣分」

## Prerequisites

Caliper is a Python CLI. Verify or install:

```bash
caliper --help          # already installed?
# If not:
uv tool install caliper           # recommended (https://docs.astral.sh/uv/)
# or: pip install caliper
```

It needs an OpenAI-compatible LLM endpoint. Any of:

```bash
# DashScope (Qwen) — cheap, good for Chinese
export DASHSCOPE_API_KEY=sk-...
export DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# DeepSeek — cheapest
export DEEPSEEK_API_KEY=sk-...

# OpenAI / OpenRouter — also supported
```

## The four commands

### 1. `caliper lint <SKILL.md>` — static check, no LLM cost

Catches rule conflicts (e.g. "always include checklist" + "skip
ceremony for trivial tasks" — both rules at once make the AI behave
erratically), missing frontmatter, description overrun, invalid YAML.

```bash
caliper lint ~/.claude/skills/my-skill/SKILL.md
```

Exit code 0 = clean, 2 = HIGH-severity findings (blocking).

**Use when:** the user shares a prompt and wants you to check it
before they ship; or a prompt is misbehaving on simple tasks.

### 2. `caliper compare <old> <new> --eval <cases.jsonl>` — head-to-head A/B

Runs both versions on the same test cases, gives you a paired
confidence interval and Hedges' g.

```bash
caliper compare seed.md challenger.md \
    --eval cases.jsonl \
    --run-dir runs/cmp-1
```

The verdict tells you:
- **CI excludes 0** → real improvement (or real regression)
- **CI crosses 0** → no statistical signal; the difference is noise

**Use when:** the user asks "is the new prompt better?" or "did this
change really help?"

### 3. `caliper iterate <seed> --eval <cases.jsonl> --rounds N` — auto loop

Full propose → lint → eval → decide loop. The AI proposes
improvements, the linter checks for conflicts, statistics decide
whether to accept. Hard `--max-cost-cny` cap so it cannot overrun budget.

```bash
caliper iterate seed.md \
    --eval cases.jsonl \
    --rounds 3 \
    --run-dir runs/iter-1 \
    --max-cost-cny 50
```

**Use when:** the user wants Caliper to automatically improve a
prompt with statistical guarantees.

### 4. `caliper analyze <SKILL.md> --eval <cases.jsonl>` — per-section attribution

Counterfactual ablation + TMC-Shapley. Tells you which paragraph
contributes how much to the final score.

```bash
caliper analyze prompt.md --eval cases.jsonl
```

**Use when:** a prompt is long (>500 lines) and the user wants to
know which sections to delete or rewrite.

## Eval JSONL format

Each line is one test case:

```json
{"id": "case-01", "input": "user prompt here", "principle": "what's being tested", "rubric": "0-10 grading rubric for the LLM judge"}
```

Aim for **n ≥ 20** for meaningful statistical power. Below n=10, the
confidence sequence will almost always be too wide to declare a winner
(this is correct conservative behavior — small samples really can't
tell signal from noise).

## Reading a verdict

A typical run-dir layout:

```
runs/my-run/
  champion.md              ← current best version
  rounds/
    round_000/
      candidate.md         ← LLM rewrite
      lint.json            ← linter findings
      skill_runs.jsonl     ← one row per eval case (with judge votes)
      verdict.json         ← BCa CI, Hedges g, CS interval, decision
  final.json               ← summary + budget + LLM usage
```

Open any `verdict.json` to see exactly **why** a candidate was accepted
or rejected.

## Common patterns to suggest to the user

- **"My prompt feels better but I'm not sure"** → run `caliper compare` against their previous version
- **"AI keeps doing X even though I told it not to"** → run `caliper lint` to find a rule conflict
- **"My prompt is too long, what can I cut?"** → run `caliper analyze` and drop sections with Shapley ≤ 0
- **"How do I improve this without burning my API budget?"** → run `caliper iterate ... --max-cost-cny 30`

## What Caliper is NOT

- Not a prompt rewriter — it measures, you decide.
- Not LLM middleware — it doesn't proxy your traffic.
- Not a managed service — runs locally, no data leaves your machine
  except what you send to your own LLM provider.
- Not free of LLM cost — your provider still charges for inference;
  Caliper just caps how much you can spend per run.

## More

- Repo: https://github.com/zhengbowenai-cmd/caliper
- Quickstart: https://github.com/zhengbowenai-cmd/caliper/blob/master/docs/quickstart.md
- Architecture: https://github.com/zhengbowenai-cmd/caliper/blob/master/docs/architecture.md
- License: MIT — fully free, forever.
