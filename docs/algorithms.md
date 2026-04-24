# Algorithms & References

Every numerical gate in Probe maps to a peer-reviewed source. When you
touch one of these modules in a PR, please cite the paper and specify
which equation / section the implementation follows.

## Statistical safety

| Module | Algorithm | Reference |
|--------|-----------|-----------|
| `safety.bootstrap.paired_bca_bootstrap` | BCa paired bootstrap | Efron, B. (1987). *Better bootstrap confidence intervals*. JASA 82(397). |
| `safety.bootstrap.hedges_g` | Hedges' g (small-sample corrected d_z) | Hedges, L. V. (1981). *Distribution theory for Glass's estimator of effect size and related estimators*. J. Educ. Stat. 6. |
| `safety.bootstrap.tost_paired` | Two One-Sided Tests (t + bootstrap) | Schuirmann, D. J. (1987). *A comparison of the two one-sided tests procedure and the power approach*. J. Pharmacokin. Biopharm. 15(6). |
| `safety.confseq.HedgedCapitalCS` | Hedged-Capital confidence sequence | Waudby-Smith, I., Ramdas, A. (2024). *Estimating means of bounded random variables by betting*. JRSSB. |
| (planned) `safety.thresholdout` | Differentially-private reusable holdout | Dwork, Feldman, Hardt, Pitassi, Reingold, Roth (2015). *Preserving statistical validity in adaptive data analysis*. STOC. |
| (planned) `safety.track_and_stop` | Fixed-confidence best-arm identification | Garivier, A., Kaufmann, E. (2016). *Optimal best arm identification with fixed confidence*. COLT. |
| (planned) `safety.drift` | Bayesian online changepoint detection | Adams, R. P., MacKay, D. J. (2007). arXiv:0710.3742. |

## Gradient source

| Module | Algorithm | Reference |
|--------|-----------|-----------|
| `gradient.replay.counterfactual_ablation` | Section-wise causal mediation | Meng, K., Bau, D., et al. (2022). *Locating and Editing Factual Associations in GPT*. (ROME). |
| `gradient.shapley.tmc_shapley` | Truncated Monte Carlo Shapley | Castro, Gomez, Tejada (2009). *Polynomial calculation of the Shapley value based on sampling*. Ghorbani & Zou (2019). *Data Shapley*. ICML. |

## Evaluator

| Module | Algorithm | Reference |
|--------|-----------|-----------|
| `evaluator.ensemble.ConservativeReward` | Ensemble disagreement penalty | Coste, T., Anwar, U., Kirk, R., Krueger, D. (2024). *Reward Model Ensembles Help Mitigate Overoptimization*. ICLR. |
| `evaluator.ensemble.EnsembleJudge._krippendorff_alpha_window` | Sliding-window inter-rater α | Krippendorff, K. (2011). *Computing Krippendorff's alpha-reliability*. |
| (planned) `evaluator.irt` | Graded Response Model (2-PL GRM) | Samejima, F. (1969). *Estimation of latent ability using a response pattern of graded scores*. Psychometrika Monograph. |
| (planned) `evaluator.dml` | Double/debiased ML for treatment effects | Chernozhukov, V., et al. (2018). Econometrics Journal 21(1). |

## Proposer

| Module | Algorithm | Reference |
|--------|-----------|-----------|
| `proposer.lagrangian.LagrangianLengthConstraint` | Primal-dual length constraint | Stooke, A., Achiam, J., Abbeel, P. (2020). *Responsive Safety in RL by PID Lagrangian*. ICML. |
| `proposer.linter.RuleConflictLinter::absolute_checklist_without_carveout` | Empirical — discovered via POC-2 H04 | — |

## Meta / known failure catalogue

Background on why each gate exists; many of these were surfaced by POC
runs rather than theory alone.

- AgenTracer — LLM failure-attribution accuracy < 10 % on complex traces.
  arXiv:2509.03312.
- MAST — 86.7 % failure rate across multi-agent frameworks.
  Cemri et al. 2025. arXiv:2503.13657.
- Arena contamination — *The Leaderboard Illusion*. Singh et al. 2025.
  arXiv:2504.20879.
- GSM-Symbolic — 3-9 % LLM accuracy drop from surface perturbation.
  Mirzadeh et al., Apple 2024. arXiv:2410.05229.
- Model collapse — Shumailov et al. 2024. Nature.
- Reward tampering — Anthropic *Sycophancy to Subterfuge*, 2024.
  arXiv:2406.10162.
- Specification gaming in reasoning models — Bondarenko et al. 2025.
  arXiv:2502.13295.
- Self-preference bias — Panickssery et al. 2024.
  *LLM Evaluators Recognize and Favor Their Own Generations*.
- Judge saturation — empirically observed in Probe POC-2 (5 of 8
  holdout cases saturated at 1.0 on both variants).
