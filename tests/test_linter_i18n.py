"""Linter Chinese + YAML block-scalar support."""

from caliper.proposer import RuleConflictLinter


def test_chinese_absolute_without_carveout_flagged():
    md = """---
name: 中文-skill
description: 处理中文任务的技能指南。
---

## 执行规则

必须始终生成详细的验证清单。

## 风格

简洁。
"""
    findings = RuleConflictLinter().lint(md)
    # Should detect absolute-checklist-without-carveout in Chinese too
    assert any(f.kind == "absolute_checklist_without_carveout" for f in findings), (
        f"Chinese 必须...验证清单 should fire. Got: {[f.kind for f in findings]}"
    )


def test_chinese_inline_carveout_passes():
    md = """---
name: 中文-skill
description: 处理中文任务的技能指南。
---

## 执行规则

总是生成验证清单，除非任务是琐碎的重命名或简单任务。
"""
    findings = RuleConflictLinter().lint(md)
    # Self-qualified with 除非/琐碎 — should NOT fire
    assert not any(f.kind == "absolute_checklist_without_carveout" for f in findings), (
        f"Self-qualified Chinese should NOT fire. Got: {[f.kind for f in findings]}"
    )


def test_yaml_block_scalar_description():
    """Linter must parse `description: |` multiline block scalars correctly."""
    md = """---
name: test
description: |
  First line of a long description that spans
  multiple lines using YAML block scalar syntax.
  This should be parsed as one string.
---

Body here.
"""
    findings = RuleConflictLinter().lint(md)
    # Should NOT complain about missing description
    assert not any(f.kind == "missing_description" for f in findings)
    assert not any(f.kind == "invalid_yaml" for f in findings)


def test_invalid_yaml_flagged():
    md = """---
name: broken
description: [unclosed-bracket
---

Body.
"""
    findings = RuleConflictLinter().lint(md)
    assert any(f.kind == "invalid_yaml" for f in findings)
