<p align="right"><a href="algorithms.md">English</a> · <b>简体中文</b></p>

# 算法 & 参考文献

Caliper 里每一个数字闸门都对应一篇同行评议的源。提 PR 动这些模块
时，请在 PR 描述里写清引用的论文、具体引用到哪一节 / 哪个公式。

## 统计安全层

| 模块 | 算法 | 引用 |
|------|------|------|
| `safety.bootstrap.paired_bca_bootstrap` | 配对 BCa 自助法 | Efron, B. (1987). *Better bootstrap confidence intervals*. JASA 82(397). |
| `safety.bootstrap.hedges_g` | Hedges' g（小样本修正的 d_z） | Hedges, L. V. (1981). *Distribution theory for Glass's estimator of effect size and related estimators*. J. Educ. Stat. 6. |
| `safety.bootstrap.tost_paired` | Two One-Sided Tests（t + bootstrap 两种） | Schuirmann, D. J. (1987). *A comparison of the two one-sided tests procedure and the power approach*. J. Pharmacokin. Biopharm. 15(6). |
| `safety.confseq.HedgedCapitalCS` | Hedged-Capital 置信序列 | Waudby-Smith, I., Ramdas, A. (2024). *Estimating means of bounded random variables by betting*. JRSSB. |
| （规划中）`safety.thresholdout` | 差分隐私可重用 holdout | Dwork, Feldman, Hardt, Pitassi, Reingold, Roth (2015). *Preserving statistical validity in adaptive data analysis*. STOC. |
| （规划中）`safety.track_and_stop` | 固定置信度最佳臂识别 | Garivier, A., Kaufmann, E. (2016). *Optimal best arm identification with fixed confidence*. COLT. |
| （规划中）`safety.drift` | 贝叶斯在线变点检测 | Adams, R. P., MacKay, D. J. (2007). arXiv:0710.3742. |

## 梯度源层

| 模块 | 算法 | 引用 |
|------|------|------|
| `gradient.replay.counterfactual_ablation` | 段级因果中介（CF 消融） | Meng, K., Bau, D., et al. (2022). *Locating and Editing Factual Associations in GPT*.（ROME） |
| `gradient.shapley.tmc_shapley` | 截断蒙特卡洛 Shapley | Castro, Gomez, Tejada (2009). Ghorbani & Zou (2019). *Data Shapley*. ICML. |

## 评估器层

| 模块 | 算法 | 引用 |
|------|------|------|
| `evaluator.ensemble.ConservativeReward` | Ensemble 分歧惩罚 | Coste, T., Anwar, U., Kirk, R., Krueger, D. (2024). *Reward Model Ensembles Help Mitigate Overoptimization*. ICLR. |
| `evaluator.ensemble.EnsembleJudge._krippendorff_alpha_window` | 滑动窗口 inter-rater α | Krippendorff, K. (2011). *Computing Krippendorff's alpha-reliability*. |
| （规划中）`evaluator.irt` | 分级响应模型（2-PL GRM） | Samejima, F. (1969). *Estimation of latent ability using a response pattern of graded scores*. Psychometrika Monograph. |
| （规划中）`evaluator.dml` | 双去偏 ML 的处理效应估计 | Chernozhukov, V., et al. (2018). Econometrics Journal 21(1). |

## 提议器层

| 模块 | 算法 | 引用 |
|------|------|------|
| `proposer.lagrangian.LagrangianLengthConstraint` | 原始-对偶长度约束 | Stooke, A., Achiam, J., Abbeel, P. (2020). *Responsive Safety in RL by PID Lagrangian*. ICML. |
| `proposer.linter.RuleConflictLinter::absolute_checklist_without_carveout` | 经验性发现 —— POC-2 H04 事故 | — |

## 元 / 已知失败模式目录

每一个闸门存在的理由，很多是 POC 运行中实际踩到的坑，不是单纯的
理论推导。

- **AgenTracer** —— LLM 对多步 trace 的归因准确率 < 10%。
  arXiv:2509.03312。
- **MAST** —— 多 agent 框架失败率高达 86.7%。
  Cemri 等 2025。arXiv:2503.13657。
- **Arena 污染** —— *The Leaderboard Illusion*。Singh 等 2025。
  arXiv:2504.20879。
- **GSM-Symbolic** —— 表面扰动导致 3-9% 准确率下降。
  Mirzadeh 等，Apple 2024。arXiv:2410.05229。
- **模型坍缩** —— Shumailov 等 2024。Nature。
- **奖励篡改** —— Anthropic *Sycophancy to Subterfuge*，2024。
  arXiv:2406.10162。
- **推理模型里的 specification gaming** —— Bondarenko 等 2025。
  arXiv:2502.13295。
- **Judge 自偏** —— Panickssery 等 2024。
  *LLM Evaluators Recognize and Favor Their Own Generations*。
- **Judge 饱和** —— Caliper POC-2 实测：8 条 holdout 里 5 条两版
  skill 都打满分，彻底不可区分。
