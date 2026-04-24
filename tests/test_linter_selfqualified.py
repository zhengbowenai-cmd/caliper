"""Regression: self-qualified absolute rules should NOT be flagged."""
from probe.proposer import RuleConflictLinter


def test_inline_exception_not_flagged():
    """POC-3 probe-iterate finding: 'Always X except Y' is properly scoped."""
    md = """---
name: test-skill
description: A test skill with a properly-scoped Always rule.
---

## Execution

Always include a verification checklist, except for trivial rename/typo tasks
where direct output is preferred.

For trivial edits, just output the code.
"""
    findings = RuleConflictLinter().lint(md)
    # Must NOT flag the Always-with-inline-exception
    assert not any(f.kind == "absolute_checklist_without_carveout" for f in findings), \
        f"Self-qualified absolute should NOT fire. Got: {[f.kind for f in findings]}"


def test_unqualified_absolute_still_flagged():
    """Control: bare Always WITHOUT inline carve-out should still fire."""
    md = """---
name: test-skill
description: A test skill with an unconditional absolute.
---

## Execution

Always include a verification checklist at the end of every response.

## Style

Write concisely.
"""
    findings = RuleConflictLinter().lint(md)
    assert any(f.kind == "absolute_checklist_without_carveout" for f in findings), \
        f"Unqualified absolute SHOULD fire. Got: {[f.kind for f in findings]}"
