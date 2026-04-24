# Changelog

All notable changes to **Caliper** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `caliper.gradient.oracle` — programmatic pass/fail checks authoritative over LLM judges.
- `caliper.gradient.replay` — section-level counterfactual ablation (CF ACE).
- `caliper.gradient.shapley` — TMC Monte-Carlo Shapley over skill sections with subset caching.
- `caliper.governance.budget` — hard wallclock / token / cost / rounds budgets.
- `caliper.proposer.lagrangian` — length constraint with dual ascent; now wired into the optimizer.
- `caliper iterate --resume` — resume a run from its existing champion.
- `caliper analyze` CLI command — runs CF + Shapley on a skill without proposing changes.
- LLM client retry with exponential backoff + token/call accounting.
- Judge result cache keyed by content hash — halves API cost on re-runs.
- Ensemble judge sliding-window Krippendorff α (default 50 items).
- Explicit `parse_error` flag on judge votes — no more silent `score=0` on API failures.
- Bootstrap TOST as a distribution-free alternative to the t-based version.
- Rule Conflict Linter:
  - Full YAML parsing (PyYAML) — handles block scalars, folded strings.
  - Multilingual support: English + 中文 absolute / qualifier term lists.
- Full type annotations, `pyright` in standard mode.
- Ruff linting + formatting with Google/Anthropic-style profile.
- GitHub Actions CI: Python 3.12 / 3.13 × Ubuntu / macOS / Windows matrix.

### Changed
- `RuleConflictLinter` no longer fires on self-qualified rules (e.g. `"Always X, except Y"`).

### Fixed
- BCa bootstrap now returns a finite CI on degenerate (zero-variance) data instead of NaN.
- Hedges' g: zero-variance-diff case treated as huge finite effect sign-preserving.

## [0.1.0] — 2026-04-23

First internal MVP.

### Added
- Core statistical safety gates: BCa bootstrap, Hedges' g, Hedged-Capital CS.
- Rule Conflict Linter (POC H04 catcher).
- Ensemble judge with Krippendorff α and conservative `mean − λ·std` reward.
- Unified OpenAI-compatible LLM client.
- `Optimizer` orchestrator and JSON-persistent run directory.
- CLI commands: `lint`, `compare`, `iterate`.
- 22 unit tests; end-to-end verification on POC-2 data.

[Unreleased]: https://github.com/OWNER/caliper/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/OWNER/caliper/releases/tag/v0.1.0
