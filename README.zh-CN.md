<p align="right"><a href="README.md">English</a> · <b>简体中文</b></p>

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/banner-dark.svg">
    <img alt="Caliper — 面向 Claude Code 的 skill 自迭代" src="assets/banner.svg" width="100%">
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
  <a href="docs/quickstart.zh-CN.md">快速上手</a> ·
  <a href="docs/architecture.zh-CN.md">架构</a> ·
  <a href="docs/algorithms.zh-CN.md">算法</a> ·
  <a href="CONTRIBUTING.zh-CN.md">贡献</a> ·
  <a href="CHANGELOG.md">更新日志</a> ·
  <a href="SECURITY.zh-CN.md">安全</a>
</p>

---

## Caliper 是个啥？

一句话：**你改了 AI 的行为指令，Caliper 告诉你这次改对了没有。**

### 一个真实的场景

你在用 Claude Code 帮你写代码。它有时候乱改不该改的地方，有时候把简单任务搞得很复杂。你写了一份"行为指南"（一个 `SKILL.md` 文件）想让它表现得更好——这事大家都干过。

改完之后，**你怎么知道你写的指南真的让它变好了？**

肉眼扫几个输出？感觉差不多？还是其实变差了你没看出来？

我们栽过这个坑：

> 一个改动在测试集上**提升 17%**，感觉很爽，准备上线。
> 换一批真实场景重新跑，**降了 8%**。
> 那 17% 全是随机噪声 —— 肉眼**根本看不出来**。

### Caliper 怎么帮你

它干一件事：**把你的新版本 vs 旧版本，跑一批测试，用数学给一个明确判决——"上"或者"别上"。**

每一次判决都告诉你：
- ✅ 哪条测试变好了 ❌ 哪条变差了
- 这个差异到底是真的，还是随机噪声
- 你的"行为指南"里**哪一段在帮忙、哪一段在拖后腿**

跟"人工 review 几个例子"不同的是：它不睡觉，每一条结论都能审计，每一次判决都有数字背书。

### 它能做的四件事

| 命令 | 它替你干啥 |
|------|----------|
| 🔍 `caliper lint <文件>` | **静态检查行为指南**——抓那种"必须 X" 和 "X 时跳过"互相打架的隐藏 bug。AI 写出来的指南最容易踩这个坑。**支持中文。** |
| 📏 `caliper compare 旧.md 新.md` | **老版本 vs 新版本对决**——告诉你"提升 17%"是真的，还是肉眼看着对、统计上其实没区别 |
| 🔄 `caliper iterate` | **完整自动循环**——让 AI 自己提议改进 → 检查无冲突 → 跑测试 → 统计通过才接受。带成本硬闸，**不会失控烧钱** |
| 🔬 `caliper analyze` | **段级解剖**——把你的指南拆成段，挨个告诉你**每一段对最终效果是加分还是减分** |

### 不会被坑的两个保证

- **完全免费、永久开源**（MIT 许可）。Caliper 本身一分钱不收。
- **绝不超支**。你 LLM 那边按 token 收费这个跑不掉，但 Caliper 内置 `--max-cost-cny 50` 这种硬闸——花到 50 块自动停，不会半夜醒来发现账户被刷爆。

---

## 一屏看完它怎么用

```bash
$ caliper compare seed.md challenger.md --eval my_cases.jsonl
```
```
                       逐条评分
+----------------------------+------+------+---------+
| id                         | seed | chal |    diff |
+----------------------------+------+------+---------+
| 01-ambiguity-cache         | 1.00 | 1.00 |   +0.00 |
| 02-over-engineering-config | 1.00 | 1.00 |   +0.00 |
| 03-defensive-sum           | 1.00 | 1.00 |   +0.00 |
| 04-surgical-bug            | 0.80 | 0.95 |   +0.15 |
| 05-trivial-rename          | 0.90 | 0.40 |   −0.50 |  ← 退步了！
| 06-pushback-singleton      | 1.00 | 1.00 |   +0.00 |
| 07-trivial-typo            | 0.90 | 0.30 |   −0.60 |  ← 退步了！
| 08-verifiable-perf         | 1.00 | 1.00 |   +0.00 |
+----------------------------+------+------+---------+

                  统计判决
+----------------+------------------------------+
| n              | 8                            |
| seed 均值      | 0.825                        |
| 候选均值       | 0.700                        |
| 平均差         | −0.125                       |
| 95% BCa 置信区间| [−0.275, +0.000]             |
| Hedges' g      | −0.42  (small)               |
| 候选 lint      | 6 条 HIGH 违规  (BLOCK)      |
+----------------+------------------------------+

→ 不要晋级
   - linter 抓到规则冲突（"总是带验证清单" 和 "琐碎任务跳过仪式" 互相打架）
   - 8 个样本下置信区间不能排除 0 ≈ 这个差异是随机的
```

**这个候选你不会上线。Caliper 在你部署之前就替你拦下了。**

---

## 安装

```bash
# 前置：装 uv （https://docs.astral.sh/uv/）
git clone https://github.com/zhengbowenai-cmd/caliper.git
cd caliper
uv sync --dev
```

Caliper 接任何 **OpenAI 兼容的 LLM** —— 阿里云 DashScope（通义）、DeepSeek、OpenAI、OpenRouter、本地 vLLM 都行。在 `.env` 里填一个就行：

```bash
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

> **完全开源、永久免费（MIT）。** Caliper 本身一分钱不收。唯一花钱的地方是你向 LLM 厂商付的推理费 —— 而且 Caliper 内置 `--max-cost-cny` 硬闸，不会有意外消费。

完整上手流程：[`docs/quickstart.zh-CN.md`](docs/quickstart.zh-CN.md)。

---

## 为什么需要这个？

人在迭代 skill 时反复栽在三个失败模式上，**现有工具一个都拦不住**：

1. **验证集过拟合。** POC 里一个 `+17%` 的"提升"，到 holdout 上变成 `-7.9%`。没置信区间根本看不出来。
2. **LLM 反思是噪声。** 你问 LLM "哪一步错了"——它的归因准确率不到 10%（AgenTracer / MAST 2025）。靠反思指导的"改进"大多是随机走步。
3. **内部规则冲突。** 一个 skill 同时说"总是要有清单" 和 "琐碎任务跳过仪式"——两条不可能同时成立。"总是"会赢，琐碎任务被仪式拖垮。

Caliper 是这三个失败模式外面的算法装甲。它**不信点估计、不信 LLM 自归因、不信内部冲突的规则**。

---

## 设计原则

| # | 原则 | 为什么 |
|---|------|--------|
| 1 | **梯度来自算法，不来自 LLM。** | 反思只能写，不能归因。用反事实重放 + TMC-Shapley 替代。 |
| 2 | **每个决策都带数学有效性。** | 不允许"点估计晋级"。BCa 自助、Hedges' g、Hedged-Capital CS —— 每一次判决都给你一个能审计的数字。 |
| 3 | **外部锚不可替代。** | 任何纯自动化系统都会陷入"自证"陷阱。Caliper 明确**显露**而非**绕过**人工签核。 |

---

## 架构（给好奇的人）

Caliper 是 8 层叠在一个 CLI 里。MVP 已交付 5 层。

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/architecture-zh-dark.svg">
    <img alt="Caliper 架构 — 八层" src="assets/architecture-zh.svg" width="100%">
  </picture>
</p>

每层算法都有论文出处。完整算法引用见 [`docs/algorithms.zh-CN.md`](docs/algorithms.zh-CN.md)，完整规范见 [`docs/architecture.zh-CN.md`](docs/architecture.zh-CN.md)。

---

## 不在范围内的事

- 微调模型权重。Caliper 只动 **skill 文本本身**。
- 替换你的 LLM。任何 OpenAI 兼容端点都行。
- 替你写文案。Caliper 负责测量，决策权在你。

---

## Demo：在真实数据上否决一次错误晋级

```bash
uv run python examples/karpathy-v2/demo.py
```

真实 POC-2 数据，4 行判决：

```
1. 针对 "+17%" 的 BCa 95% CI：     [-0.175, +0.000]   → n=8 下不显著
2. 检测 d=0.3 至 80% 功效需 n：    ~88               → POC 只有 n=8 (~15% 功效)
3. Peek-safe CS：n≤8 时一直 False                    → 晋级会被闸门拦下
4. best.md 上 Linter 6 条 HIGH 违规，含 POC-2 H04 模式
```

三道独立闸门 —— 任何一个单独都足以否决那次错误晋级。

---

## 贡献

遵循现代 Python 工程标准，详见 [`CONTRIBUTING.zh-CN.md`](CONTRIBUTING.zh-CN.md)。

`ruff`（格式化 + lint）· `pyright`（类型）· `pytest`（46/46 通过）· `pre-commit` · `gitleaks` · CodeQL · CI 矩阵：Python 3.12 / 3.13 × Ubuntu / macOS / Windows。

---

## 致谢

- [`anthropics/skills`](https://github.com/anthropics/skills) —— SKILL.md 格式和 `skill-creator` 启发
- [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent) —— `skill_manager_tool.py` 的设计参考
- [`gepa-ai/gepa`](https://github.com/gepa-ai/gepa) —— prompt 进化的 baseline
- [`UKGovernmentBEIS/inspect_ai`](https://github.com/UKGovernmentBEIS/inspect_ai) —— evaluation 框架惯例

---

## 许可

MIT —— 永久免费、完全开源。详见 [`LICENSE`](LICENSE)。
