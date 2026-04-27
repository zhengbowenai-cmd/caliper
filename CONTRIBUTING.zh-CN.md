<p align="right"><a href="CONTRIBUTING.md">English</a> · <b>简体中文</b></p>

# 贡献指南

感谢你来贡献代码。Caliper 的价值建立在**数学严谨性** + **可验证声明**
上，请和我们一起守住这两条。

## 基本规则

1. **每一个算法都要有出处。** 如果是新提出的方法，请在 PR 里写明
   并用一个 test 做经验证实。
2. **每一个闸门都有对应测试。** 修 bug 时同时加 regression test，
   防止同类 bug 悄悄回归。
3. **禁用点估计声明。** PR 说"指标 X 提升了 Y"时，必须附带置信
   区间或可复现的 benchmark。
4. **类型先行。** 所有公开接口必须有类型注解，且能通过
   `pyright` standard 模式。

## 开发环境

```bash
# 还没装 uv？https://docs.astral.sh/uv/
git clone https://github.com/zhengbowenai-cmd/caliper.git
cd caliper
uv sync --dev                         # 依赖 + 开发工具
uv run pre-commit install             # 装 git hooks
```

### 日常开发循环

```bash
uv run ruff format .                  # 自动格式化
uv run ruff check --fix .             # Lint + autofix
uv run pyright                        # 类型检查
uv run pytest -x --cov=caliper        # 测试 + 覆盖率
```

### 本地跑 CLI

```bash
# 对 seed skill 做 lint 烟测
uv run caliper lint examples/karpathy-v2/seed_skill.md

# 无 LLM 调用，replay POC-2 数据验证
uv run python examples/karpathy-v2/demo.py
```

## 分支 & 提交规范

- **分支：** `feature/…`、`fix/…`、`docs/…`、`chore/…`、`refactor/…`
- **提交信息：** 祈使句、现在时。宽松的
  [Conventional Commits](https://www.conventionalcommits.org/) 风格：

  ```
  feat(safety): add Thresholdout with DP-bounded holdout reuse
  fix(linter): handle YAML block scalars in description field
  docs(architecture): expand Ground Truth Layer section
  ```

## PR checklist

发起 PR 前，请确认：

- [ ] `ruff format --check .` 通过
- [ ] `ruff check .` 通过（任何 `# noqa` 必须说明原因）
- [ ] `pyright` 在 standard 模式下通过
- [ ] `pytest` 全绿，包含任何新加的 regression test
- [ ] 新外部依赖在 PR 正文里有理由说明
- [ ] CHANGELOG.md 的 `[Unreleased]` 段已更新
- [ ] 如果行为变了，README / docs 也已更新

## 提 issue

请使用 [issue 模板](.github/ISSUE_TEMPLATE/) —— 模板要求最小
复现 + 环境信息，triage 会快很多。

## 安全

安全漏洞**不要**提公开 issue。请看 [SECURITY.zh-CN.md](SECURITY.zh-CN.md)。

## Code of Conduct

参与即视为同意遵守
[Contributor Covenant](CODE_OF_CONDUCT.md)。
