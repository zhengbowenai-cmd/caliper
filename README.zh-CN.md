<p align="right"><a href="README.md">English</a> · <b>简体中文</b></p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img alt="Caliper — 面向 Claude Code 的 skill 自迭代" src="assets/banner.svg" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/zhengbowenai-cmd/caliper/actions"><img src="https://img.shields.io/github/actions/workflow/status/zhengbowenai-cmd/caliper/ci.yml?branch=main&label=CI&style=flat-square" alt="CI"/></a>
  <a href="https://github.com/zhengbowenai-cmd/caliper/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License"/></a>
  <img src="https://img.shields.io/badge/python-3.12%20%7C%203.13-informational?style=flat-square" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/types-pyright-forestgreen?style=flat-square" alt="Pyright"/>
  <img src="https://img.shields.io/badge/lint-ruff-orange?style=flat-square" alt="Ruff"/>
</p>

<p align="center">
  <a href="docs/quickstart.zh-CN.md">快速上手</a> ·
  <a href="docs/architecture.zh-CN.md">架构</a> ·
  <a href="docs/algorithms.zh-CN.md">算法</a> ·
  <a href="CONTRIBUTING.zh-CN.md">贡献</a> ·
  <a href="CHANGELOG.md">更新日志</a> ·
  <a href="SECURITY.zh-CN.md">安全</a>
</p>

---

## 为什么要有 Caliper？

我们在 Claude Code 的 skill 自迭代循环上做了两轮 POC，暴露出三个反复
出现、现有闸门完全拦不住的失败模式：

1. **验证集过拟合。** 验证集上看到的 `+17%` 收益，换到 holdout 集一跑
   变成 `-7.9%`。
2. **LLM 反思是噪声，不是梯度。** 多步 trace 上的归因准确率 < 10%
   （AgenTracer / MAST 2025）。
3. **规则内部冲突。** GEPA 产出的 skill 里，
   *"始终生成验证清单"* 悄悄覆盖了 *"琐碎任务跳过仪式"*，让每个简单
   任务都被仪式拖垮。

**Caliper** 就是这个循环外面的一层算法装甲。它不是"换一个 prompt"的
方案，而是在每个决策点都装上有统计保证的测量器。三个已验证的闸门
在真实 POC-2 数据上**各自足以阻止那次错误晋级**。

---

## 设计原则（不可协商）

| # | 原则 | 含义 |
|---|------|------|
| 1 | **梯度来自算法，不来自 LLM。** | 反思只能写，不能归因。用反事实重放 + TMC-Shapley 替代。 |
| 2 | **每个决策都带数学有效性。** | 不允许"点估计晋级"。BCa 自助、Hedges' g、Hedged-Capital CS——每一次判决都写进 `verdict.json`。 |
| 3 | **外部锚不可替代。** | 任何纯算法系统都会陷入"自证"陷阱。Caliper 明确**显露**而非**绕过**人工签核和真实用户信号。 |

---

## 安装

```bash
# 推荐用 uv（https://docs.astral.sh/uv/，无系统 Python 污染）
uv tool install caliper

# 从源码安装
git clone https://github.com/zhengbowenai-cmd/caliper.git
cd caliper
uv sync --dev
```

运行时需要一个 **OpenAI 兼容的 LLM 接口**。已测试：阿里云 DashScope
（通义）、DeepSeek、OpenAI、OpenRouter。

```bash
# .env
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

---

## 快速上手

四个 CLI 命令，Rich 终端输出，所有产物落盘成 JSON。

```bash
# 1. 静态 Lint —— 抓 POC H04 "Always X + 平凡例外" 冲突、
#    YAML 错误、description 超长。支持中英文。
caliper lint 路径/SKILL.md

# 2. 段级归因 —— 反事实消融 + TMC-Shapley。
#    告诉你 skill 的每一段到底在不在拉分。
caliper analyze skill.md --eval cases.jsonl

# 3. 一对一对比 —— 配对 BCa 自助法 + Hedges' g + peek-safe CS + Linter。
caliper compare seed.md challenger.md --eval cases.jsonl --run-dir runs/x

# 4. 完整优化循环 —— propose → lint → eval → decide,并带成本硬闸。
caliper iterate seed.md --eval cases.jsonl --rounds 3 \
    --run-dir runs/my-run \
    --judge-models qwen3.6-plus,qwen-max,qwen-plus \
    --max-cost-cny 50 \
    --cs-margin 0.02
```

### Eval 文件格式 (`*.jsonl`)

```json
{"id": "case-01", "input": "用户 prompt", "principle": "测试的原则", "rubric": "判官 0-10 打分准则"}
```

### Run 目录布局

```
runs/my-run/
  config.json                 冻结的 OptimizerConfig
  seed_skill.md               起始 SKILL.md
  champion.md                 当前冠军（晋级时更新）
  rounds/
    round_000/
      candidate.md            LLM 重写的候选
      lint.json               Lint 发现 JSON
      skill_runs.jsonl        每个 eval case 一条 SkillRun（含判官投票）
      verdict.json            BCa CI + Hedges g + CS CI + 决策 + 理由
    round_001/ ...
  final.json                  总结 + 预算 + LLM 使用量 + 缓存统计
```

---

## 架构

共 8 层，MVP 已交付 5 层。完整规范见
[`docs/architecture.md`](docs/architecture.md)，每一条算法引用见
[`docs/algorithms.md`](docs/algorithms.md)。

```
┌────────────────────────────────────────────────────────────────────┐
│ 地面真值层      用户信号 · 配对对战 · 外部基准                          │ V2
├────────────────────────────────────────────────────────────────────┤
│ 统计安全层      BCa · Hedges g · TOST · Hedged-Capital CS ·          │
│                Thresholdout · Track-and-Stop · BOCPD                │
├────────────────────────────────────────────────────────────────────┤
│ 梯度源层        反事实重放 · TMC-Shapley · Oracle                     │
│                （替代 LLM 自反思）                                    │
├────────────────────────────────────────────────────────────────────┤
│ 评估器层        判官合奏 · Krippendorff α · IRT · DML                 │
├────────────────────────────────────────────────────────────────────┤
│ 提议器层        LLM 重写器 · 规则冲突 Linter · Lagrangian 长度         │
├────────────────────────────────────────────────────────────────────┤
│ 归档层          MAP-Elites · Round-0 锚点 · Pareto 入档                │ V2
├────────────────────────────────────────────────────────────────────┤
│ 治理层          能力清单 · 成本预算 · 权限信封                          │
├────────────────────────────────────────────────────────────────────┤
│ 运行时层        Claude Code · Hermes · Langfuse ·                    │
│                Inspect AI · GEPA（全部可替换 adapter）                 │
└────────────────────────────────────────────────────────────────────┘
```

### 已交付模块

| 路径 | 作用 | 参考文献 |
|------|------|---------|
| `caliper.safety.bootstrap` | 配对 BCa 自助 · Hedges' g · TOST · 功效分析 | Efron 1987 · Hedges 1981 · Schuirmann 1987 |
| `caliper.safety.confseq` | Hedged-Capital CS——随时 peek 不伤 Type-I | Waudby-Smith & Ramdas 2024 JRSSB |
| `caliper.gradient.oracle` | 程序化 pass/fail 检查 | — |
| `caliper.gradient.replay` | 段级反事实消融 | Meng 等 2022 (ROME) |
| `caliper.gradient.shapley` | TMC 蒙特卡洛 Shapley | Castro 等 2009 · Ghorbani-Zou 2019 |
| `caliper.evaluator.ensemble` | 多家族判官 · Krippendorff α · 结果缓存 | Coste 等 2024 ICLR · Krippendorff 2011 |
| `caliper.proposer.linter` | 规则冲突 Linter（中英文） | POC-2 H04 |
| `caliper.proposer.lagrangian` | 长度约束 + 对偶上升 | Stooke 等 2020 |
| `caliper.proposer.rewriter` | LLM 重写器（后续可替换为 GEPA/Shapley 驱动） | — |
| `caliper.governance.budget` | Token / 时长 / 成本 / 轮次 预算 | — |
| `caliper.runtime.llm` | 带重试 + token 计数的 OpenAI 兼容客户端 | — |
| `caliper.optimizer` | 串起所有闸门的编排器 | — |
| `caliper.cli` | `caliper lint / analyze / compare / iterate` | — |
| `caliper.persistence` | JSON run-dir 布局 · SkillRun 序列化 | — |
| `caliper.schemas` | `SkillRun`, `CIResult`, `Decision`, `EffectSize` | — |

---

## Demo：在真实数据上否决一次错误晋级

```bash
uv run python examples/karpathy-v2/demo.py
```

在真实的 POC-2 数据上跑会输出：

```
1. 针对 "+17%" 的 BCa 95% CI：  [-0.175, +0.000]   → n=8 下不显著
2. 检测 d=0.3 至 80% 功效所需 n：  ~88              → POC 只有 n=8 (~15% 功效)
3. Peek-safe CS：n≤8 时 "wins?" 一直 False         → 晋级会被闸门拦下
4. Linter 在 best.md 上发现 6 条 HIGH 违规，包含 POC-2 H04 模式
```

三重独立闸门——任何一个单独都足以拦下那次错误晋级。

---

## 贡献

见 [`CONTRIBUTING.md`](CONTRIBUTING.md)。

- 格式化 + Lint：[`ruff`](https://docs.astral.sh/ruff/)
- 类型检查：[`pyright`](https://github.com/microsoft/pyright)（标准模式）
- 测试：`pytest` + 覆盖率（`--cov=caliper`）
- Pre-commit：`pre-commit install && pre-commit run --all-files`
- CI：GitHub Actions 矩阵（Python 3.12/3.13 × Ubuntu/macOS/Windows）
- 安全扫描：CodeQL

---

## 安全

安全漏洞**请勿**公开提 issue——请看
[`SECURITY.md`](SECURITY.md) 或使用 GitHub Private Vulnerability Reporting。

---

## 致谢

- [anthropics/skills](https://github.com/anthropics/skills) —— SKILL.md 格式和 `skill-creator` 启发
- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) —— `skill_manager_tool.py` 的设计参考
- [gepa-ai/gepa](https://github.com/gepa-ai/gepa) —— prompt 进化的 baseline
- [UKGovernmentBEIS/inspect_ai](https://github.com/UKGovernmentBEIS/inspect_ai) —— evaluation 框架惯例

---

## 许可

MIT —— 见 [`LICENSE`](LICENSE)。
