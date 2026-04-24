<!--
Thanks for your PR!  Before opening, confirm the boxes below.
Small PRs merged quickly; huge PRs take longer — please split if you can.
-->

## What

Short, one-paragraph summary of the change. Link to the issue(s) it closes.

Closes #

## Why

What failure mode, user request, or paper motivates this change?

## How

Notable implementation choices, trade-offs, and anything a reviewer should focus on.

## Evidence

- [ ] New or updated tests cover the change
- [ ] If performance / statistical behavior changed, include a before/after benchmark or CI
- [ ] Docs updated (README / `docs/`)
- [ ] CHANGELOG.md updated under `[Unreleased]`

## Quality gates

- [ ] `ruff format --check .` passes
- [ ] `ruff check .` passes
- [ ] `pyright` passes
- [ ] `pytest` passes
- [ ] No new secrets, API keys, or fixture data larger than ~10 KB
