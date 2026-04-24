# Contributing to Probe

Thank you for considering a contribution. Probe's value depends on
mathematical rigor and verifiable claims — please help us keep both.

## Ground rules

1. **Every algorithm we ship cites its source.** If the claim is new, call it out
   and justify empirically in a test.
2. **Every gate is backed by a test.** Add a regression test when fixing a
   bug so it can't silently return.
3. **No point-estimate claims.** If a PR says "improves X", the PR description
   must include a confidence interval or reproducible benchmark.
4. **Types come first.** All public interfaces must carry type annotations and
   pass `pyright` in standard mode.

## Developer setup

```bash
# install uv if you don't have it: https://docs.astral.sh/uv/
git clone https://github.com/OWNER/probe.git
cd probe
uv sync --dev                         # install deps + dev extras
uv run pre-commit install             # set up git hooks
```

### Daily dev loop

```bash
uv run ruff format .                  # auto-format
uv run ruff check --fix .             # lint + autofix
uv run pyright                        # type check
uv run pytest -x --cov=probe          # tests with coverage
```

### Running the CLI locally

```bash
# smoke-test lint
uv run probe lint examples/karpathy-v2/seed_skill.md

# replay POC-2 audit without any LLM calls
uv run python examples/karpathy-v2/demo.py
```

## Branch & commit conventions

- **Branches:** `feature/…`, `fix/…`, `docs/…`, `chore/…`, `refactor/…`.
- **Commits:** imperative, present tense. We use a loose
  [Conventional Commits](https://www.conventionalcommits.org/) style:

  ```
  feat(safety): add Thresholdout with DP-bounded holdout reuse
  fix(linter): handle YAML block scalars in description field
  docs(architecture): expand Ground Truth Layer section
  ```

## Pull request checklist

Before opening a PR, please confirm:

- [ ] `ruff format --check .` passes
- [ ] `ruff check .` passes (no warnings ignored via `# noqa` without justification)
- [ ] `pyright` passes in standard mode
- [ ] `pytest` passes, including any new regression tests
- [ ] New external deps are justified in the PR body
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] README / docs updated if behavior changed

## Reporting issues

Please use the [issue templates](.github/ISSUE_TEMPLATE/) — they ask for the
minimal reproducer and environment details that make triage much faster.

## Security

Do **not** open public issues for security findings. See
[SECURITY.md](SECURITY.md).

## Code of conduct

By participating you agree to the [Contributor Covenant](CODE_OF_CONDUCT.md).
