# Quickstart

From zero to your first gated optimization run in ~10 minutes.

## 0. Install

```bash
# Install uv (https://docs.astral.sh/uv/) if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
# or: powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows

git clone https://github.com/OWNER/caliper.git
cd caliper
uv sync --dev
```

## 1. Bring a provider key

Caliper talks to any OpenAI-compatible LLM. DashScope / Qwen works well
and is inexpensive for Chinese users.

```bash
cp .env.example .env            # if we ship one later
# Edit .env:
# DASHSCOPE_API_KEY=sk-...
# DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

Or export directly:

```bash
export DASHSCOPE_API_KEY=sk-...
export DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## 2. Lint a skill

```bash
uv run caliper lint ~/.claude/skills/my-skill/SKILL.md
```

Exit code 0 = clean. Exit code 2 = HIGH findings (rule conflict, missing
frontmatter, description too long, etc.). The linter supports English
and Chinese skills.

## 3. Write a small eval set

Create `eval.jsonl`:

```json
{"id": "c01", "input": "add caching to my function", "principle": "ambiguity", "rubric": "Score 10 if the response asks for cache type/TTL/function signature before writing code. Score 0 if it silently picks an approach."}
{"id": "c02", "input": "rename x to count in 'x = 0'", "principle": "no ceremony on trivial", "rubric": "Score 10 if it outputs 'count = 0' directly. Score 0 if it adds commentary, checklists, or questions."}
```

Aim for **n ≥ 20** for realistic statistical power. n = 5 is enough to
smoke-test the pipeline but will almost never promote.

## 4. Compare two versions

```bash
uv run caliper compare seed.md challenger.md \
    --eval eval.jsonl \
    --run-dir runs/cmp-1
```

Output: per-case scores, paired BCa 95% CI on the diff, Hedges' g,
Confidence Sequence CI, and linter findings for both sides.

## 5. Run the full loop with a budget cap

```bash
uv run caliper iterate seed.md \
    --eval eval.jsonl \
    --rounds 3 \
    --run-dir runs/iter-1 \
    --judge-models qwen3.6-plus,qwen-max \
    --max-cost-cny 20          # hard ceiling
```

Progress streams to stdout; full artifacts land in the run dir. Tail any
`verdict.json` to see exactly why a round was accepted or rejected.

## 6. Inspect the champion and artifacts

```bash
cat runs/iter-1/final.json | jq
cat runs/iter-1/champion.md
cat runs/iter-1/rounds/round_000/verdict.json | jq
```

## 7. When a run is wrong — what to investigate

1. **Linter fired unexpectedly?** Look at `rounds/round_N/lint.json`
   — each finding includes the literal line that matched.
2. **Run burned through budget with no accept?** Check
   `final.json.budget` — common cause is judge parse errors (check
   `meta.any_parse_error` in skill runs).
3. **CS lower bound stuck at -1?** You have too few eval cases. CS
   needs n ≳ 20 on a paired comparison before the interval starts
   narrowing meaningfully.

## 8. Next: per-section attribution

```bash
uv run caliper analyze skill.md --eval eval.jsonl --permutations 15
```

Tells you which sections of your skill are contributing. Drop or
condense sections with Shapley φ near zero.

---

For the philosophy, see [`architecture.md`](architecture.md). For the
math, see [`algorithms.md`](algorithms.md).
