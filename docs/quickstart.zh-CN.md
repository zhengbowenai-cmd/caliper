<p align="right"><a href="quickstart.md">English</a> · <b>简体中文</b></p>

# 快速上手

从 0 到一次"带闸门的"真实优化运行，大约 10 分钟。

## 0. 安装

```bash
# 如果你还没装 uv（https://docs.astral.sh/uv/）：
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
# 或：powershell -c "irm https://astral.sh/uv/install.ps1 | iex"   # Windows

git clone https://github.com/zhengbowenai-cmd/caliper.git
cd caliper
uv sync --dev
```

## 1. 准备 LLM key

Caliper 只要你接入一个 OpenAI 兼容的 LLM。国内用户推荐阿里云
DashScope（通义），便宜、快、稳定。

```bash
cp .env.example .env
# 编辑 .env：
# DASHSCOPE_API_KEY=sk-...
# DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

或者直接导出环境变量：

```bash
export DASHSCOPE_API_KEY=sk-...
export DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

## 2. Lint 一个 skill

```bash
uv run caliper lint ~/.claude/skills/my-skill/SKILL.md
```

退出码 0 = 干净。退出码 2 = 存在 HIGH 级别问题（规则冲突、缺
frontmatter、description 超长等）。Linter 同时支持中英文 skill。

## 3. 写一个小的 eval 集

创建 `eval.jsonl`：

```json
{"id": "c01", "input": "给我的函数加缓存", "principle": "歧义——应该先问清楚", "rubric": "如果回答先问了缓存类型/TTL/函数签名再写代码，给 10 分。如果闷头猜一个实现方式，给 0 分。"}
{"id": "c02", "input": "把 'x = 0' 里的 x 改名为 count", "principle": "琐碎任务不加仪式", "rubric": "如果直接输出 'count = 0'，给 10 分。如果加注释、提问、列出 tradeoff，给 0 分。"}
```

**建议 n ≥ 20** 才能得到有意义的统计功效。n = 5 只够冒烟测试，几乎
永远无法晋级（这是正确的保守行为）。

## 4. 一对一对比两个版本

```bash
uv run caliper compare seed.md challenger.md \
    --eval eval.jsonl \
    --run-dir runs/cmp-1
```

输出：每条 case 的分数、针对 diff 的配对 BCa 95% CI、Hedges' g、
Confidence Sequence CI、两边的 Lint 发现。

## 5. 完整循环 + 成本硬闸

```bash
uv run caliper iterate seed.md \
    --eval eval.jsonl \
    --rounds 3 \
    --run-dir runs/iter-1 \
    --judge-models qwen3.6-plus,qwen-max \
    --max-cost-cny 20          # 花超 ¥20 强制停
```

进度实时输出到 stdout；所有产物落在 run dir。查看任一
`verdict.json` 就知道这一轮为什么被接受 / 拒绝。

## 6. 查看 champion + 历史

```bash
cat runs/iter-1/final.json | jq
cat runs/iter-1/champion.md
cat runs/iter-1/rounds/round_000/verdict.json | jq
```

## 7. 结果不对时怎么排查

1. **Linter 意外报错？** 看 `rounds/round_N/lint.json` ——
   每条发现都带原文命中的那一行。
2. **烧完预算都没晋级？** 看 `final.json.budget` ——
   常见原因是判官解析失败（看 skill_runs 的 `meta.any_parse_error`）。
3. **CS 下界一直卡在 -1？** eval case 太少了。配对比较下，CS 通常
   要到 n ≳ 20 才开始明显收窄。

## 8. 深入：段级归因

```bash
uv run caliper analyze skill.md --eval eval.jsonl --permutations 15
```

输出每一段的 Shapley φ——告诉你哪些段真的在拉分，哪些在拖分。
φ 接近 0 的段可以考虑合并或删除。

---

设计哲学见 [`architecture.md`](architecture.md)，完整算法引用见
[`algorithms.md`](algorithms.md)。
