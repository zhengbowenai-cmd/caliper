<p align="right"><a href="architecture.md">English</a> · <b>简体中文</b></p>

# Caliper 架构

> 本文描述 V1 完整架构。MVP 已交付 **统计安全层**、**梯度源层**、
> **提议器层**、**评估器层**、**治理层** 共五层。标记 *V2* 的是规划中。

## 三条不可协商的设计公理

1. **梯度来自算法，不来自 LLM。** 反思对失败的归因在多步 trace 上
   准确率 < 10%（AgenTracer、MAST 实测）。Caliper 用"反事实重放 +
   TMC-Shapley"取代"问 LLM 哪里错了"。
2. **每个决策都带数学有效性。** 仅点估计永远无法让候选晋级；只有
   **配对 BCa 自助 95% CI 排除 0** 且 **置信序列下界超过预登记
   margin** 才会晋级。
3. **外部锚不可替代。** 任何纯算法的防线都会被"自证"陷阱慢慢穿透
   ——真实用户信号 + 人工签核是 safety-critical 晋级的必需品。

## 八层架构

```
┌────────────────────────────────────────────────────────────────────┐
│ 地面真值层       用户信号 · 配对对战 · 外部基准                       │ V2
├────────────────────────────────────────────────────────────────────┤
│ 统计安全层       Thresholdout · Hedged-Cap CS · BCa · TOST ·         │
│                 Hedges · BOCPD（漂移）· Track-and-Stop BAI           │
├────────────────────────────────────────────────────────────────────┤
│ 梯度源层         反事实重放 · TMC-Shapley · Oracle                   │
│                 （替代 LLM 自反思）                                   │
├────────────────────────────────────────────────────────────────────┤
│ 评估器层         多家族 judge · Krippendorff α · IRT-GRM ·            │
│                 DML · Causal Forest · meta-judge 周期校准              │
├────────────────────────────────────────────────────────────────────┤
│ 提议器层         LLM 重写器 · 规则冲突 Linter · Lagrangian 长度约束   │
├────────────────────────────────────────────────────────────────────┤
│ 归档层           MAP-Elites · Pareto 入档 · Round-0 锚点（不可变）    │ V2
├────────────────────────────────────────────────────────────────────┤
│ 治理层           能力清单 · 成本预算 · 权限信封 · 人工签核闸门          │
├────────────────────────────────────────────────────────────────────┤
│ 运行时层         Claude Code · Hermes skill-manager ·                 │
│                 Langfuse · Inspect AI · GEPA（可替换 adapter）         │
└────────────────────────────────────────────────────────────────────┘
```

## 一次完整的优化轮

```
propose ─▶ lint ─▶ judge-panel eval ─▶ bootstrap CI ─▶ CS update ─▶ decide
   ▲         │          │                    │              │          │
   │         └──HIGH:REJECT                  │              │          │
   │                    │           not sig ─┤         below ─┤         │
   └────────── reject ◄─┴────────────────────┴──────────────┘          │
                                                                       ▼
                                                   ACCEPT: champion ← candidate
```

**每一次拒绝都把"拒绝理由"写进 `verdict.json`**。没有静默丢弃。

## 闸门链 —— 拒绝理由一览

| 闸门 | 模块 | 触发条件 | 典型成因 |
|------|------|---------|---------|
| Linter | `caliper.proposer.linter` | 任意 HIGH 发现 | 规则冲突、frontmatter 超长 |
| Judge panel | `caliper.evaluator.ensemble` | 全体 judges 返回 parse_error | rubric 对不上、LLM 拒答 |
| Bootstrap CI | `caliper.safety.bootstrap` | 95% CI 跨 0 | n 太小、指标噪声大 |
| CS | `caliper.safety.confseq` | 下界 ≤ margin | 序贯 peek 下证据不足 |
| Budget | `caliper.governance.budget` | 时长 / token / 成本 / 轮次 超限 | — |

## 数据契约 —— `SkillRun`

每个组件都读写同一个 schema。见
[`src/caliper/schemas.py`](../src/caliper/schemas.py)。

```python
class SkillRun(BaseModel):
    id: str
    skill_version_hash: str
    input: str
    response: str
    trace: list[TraceStep]
    oracle: OracleResult | None       # 存在时具有权威性
    judges: list[JudgeScore]          # 多家族
    theta_irt: float | None           # V2 —— IRT-GRM 潜能力
    user_signal: UserSignal | None    # V2 —— Claude Code hooks
    shapley: dict[str, float]         # section_id -> phi_i
    cf_diff: dict[str, str]
    meta: dict[str, Any]
```

持久化：每条 SkillRun 一行 JSON，落在
`runs/<run>/rounds/round_NNN/skill_runs.jsonl`。纯文本，jq / DuckDB
等外部工具可以直接查。

## **不在**范围内的事

- 微调模型权重。Caliper 只动 skill 文本。
- 运行任意用户工具。执行仍然走 Claude Code 自己的 tool-use；
  Caliper 只管写 SKILL.md。
- 替换 LLM 本体。Caliper 是 provider 无关的——自带一个 OpenAI
  兼容的 endpoint 即可。

## 所有外部系统都是可替换的 adapter

| Caliper 接口 | 当前 adapter | 可替换为 |
|-------------|------------|---------|
| `LLMClient` | OpenAI SDK + `api_base` 覆写 | Anthropic Messages SDK、vLLM、本地模型 |
| `ensemble.EnsembleJudge` | 按 case 并发调用 | Inspect AI Scorer |
| Skill CRUD | —（V1 暂未集成） | Hermes `skill_manager_tool.py` |
| Trace sink | 本地 JSONL | Langfuse |
| Proposer | `NaiveRewriter` | GEPA `optimize_anything`、DSPy `GEPA` |

## 引用

全部算法引用见 [`docs/algorithms.zh-CN.md`](algorithms.zh-CN.md) /
[`docs/algorithms.md`](algorithms.md)。
