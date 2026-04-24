"""Tests for proposer.linter — the POC H04 guard."""

from caliper.proposer import RuleConflictLinter


def test_catches_poc2_h04_pattern():
    """POC-2 best.md had 'Always conclude with checklist' + 'Trivial Exception'.

    Linter MUST flag this.
    """
    bad_md = """---
name: karpathy-v2
description: Guidelines for careful coding with a trivial exception for simple tasks.
---

## 1. Context Protocol
- **Trivial Exception:** If the task is completely unambiguous, skip assumptions and output only the code.

## 4. Output Formatting
- **Success Criteria:** Always conclude with a brief, verifiable checklist.
"""
    linter = RuleConflictLinter()
    findings = linter.lint(bad_md)
    assert any(f.kind == "absolute_checklist_without_carveout" for f in findings), (
        f"Expected POC H04 pattern to fire. Got: {[f.kind for f in findings]}"
    )
    assert linter.has_blocking_findings(findings)


def test_clean_skill_passes():
    good_md = """---
name: karpathy-guidelines
description: Behavioral guidelines to reduce common LLM coding mistakes.
---

# Karpathy Guidelines

Think before coding. Surface tradeoffs. Make surgical changes.

For trivial edits, just do the edit.
"""
    linter = RuleConflictLinter()
    findings = linter.lint(good_md)
    # Must not have HIGH findings (absolute words + clear language is fine)
    assert not linter.has_blocking_findings(findings)


def test_description_length_cap():
    long_desc = "x" * 2000
    md = f"""---
name: foo
description: {long_desc}
---

Body.
"""
    findings = RuleConflictLinter(description_char_limit=1024).lint(md)
    assert any(f.kind == "description_too_long" for f in findings)


def test_missing_frontmatter():
    md = "# No frontmatter here\n\nJust markdown."
    findings = RuleConflictLinter().lint(md)
    assert any(f.kind == "missing_frontmatter" for f in findings)


def test_missing_name_field():
    md = """---
description: Only description here, no name field.
---

Body.
"""
    findings = RuleConflictLinter().lint(md)
    assert any(f.kind == "missing_name" for f in findings)
