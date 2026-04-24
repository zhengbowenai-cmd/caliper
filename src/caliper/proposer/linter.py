"""Rule Conflict Linter — scans a SKILL.md for internally contradictory rules.

Motivation (POC-2 H04 evidence)
-------------------------------
GEPA's reflection LM produced a SKILL.md with:
  Section 1:  "Trivial Exception: skip assumptions for unambiguous tasks"
  Section 4:  "Always conclude with a brief, verifiable checklist"
On a trivial "delete a comment" request, the `Always checklist` rule
fired and tanked the score. No existing defense caught this.

The fix: lint every candidate BEFORE promoting. If an absolute rule
("always/must/never") can conflict with a qualified rule ("exception/
skip/only when/trivial"), flag it.

This is conservative: false positives are fine (they force the LLM to
clarify), false negatives are the cost.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

import yaml  # PyYAML — handles block scalars, folded, etc.


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class LintFinding:
    kind: str
    severity: Severity
    message: str
    evidence: list[str]       # literal lines that triggered the finding


# --- pattern libraries ------------------------------------------------

# Absolute directives: rules that claim to apply universally.
# English + Chinese support — both languages are valid for SKILL.md.
ABSOLUTE_PATTERNS = [
    # English
    re.compile(r"\balways\b", re.I),
    re.compile(r"\bnever\b", re.I),
    re.compile(r"\bmust\b", re.I),
    re.compile(r"\bmandatory\b", re.I),
    re.compile(r"\brequired\b", re.I),
    re.compile(r"\bevery (?:time|case|response|turn)\b", re.I),
    re.compile(r"\ball (?:of the time|tasks|cases|situations)\b", re.I),
    re.compile(r"\bwithout (?:exception|fail)\b", re.I),
    # Chinese
    re.compile(r"总是"), re.compile(r"必须"), re.compile(r"一定要"),
    re.compile(r"严禁"), re.compile(r"绝对"), re.compile(r"永远不"),
    re.compile(r"每次"), re.compile(r"所有时候"), re.compile(r"无一例外"),
    re.compile(r"强制"), re.compile(r"不得不"),
]

# Qualified-exception directives: rules that create carve-outs.
QUALIFIER_PATTERNS = [
    # English
    re.compile(r"\btrivial\b", re.I),
    re.compile(r"\bexception\b", re.I),
    re.compile(r"\bskip\b", re.I),
    re.compile(r"\bomit\b", re.I),
    re.compile(r"\bonly (?:if|when)\b", re.I),
    re.compile(r"\bunless\b", re.I),
    re.compile(r"\bdo not\b", re.I),
    re.compile(r"\bdon.?t\b", re.I),
    re.compile(r"\bwhen (?:applicable|relevant|needed)\b", re.I),
    # Chinese
    re.compile(r"除非"), re.compile(r"例外"), re.compile(r"跳过"),
    re.compile(r"忽略"), re.compile(r"只有当"), re.compile(r"仅当"),
    re.compile(r"不适用"), re.compile(r"可以省略"), re.compile(r"琐碎"),
    re.compile(r"简单任务"), re.compile(r"简单情况"),
]

# Bloat heuristics
TOP_LEVEL_HEADING_RE = re.compile(r"^\s*#{1,3}\s", re.M)
CHECKLIST_LINE_RE = re.compile(r"^\s*(?:-|\*|\d+\.)\s*\[?.?\]?\s", re.M)


# --- extraction ---------------------------------------------------------


def _split_sections(md: str) -> list[tuple[str, str]]:
    """Return list of (heading, body) sections from markdown."""
    parts = re.split(r"(?m)^(#{1,4}\s.+)$", md)
    # parts = [preamble, heading1, body1, heading2, body2, ...]
    sections: list[tuple[str, str]] = []
    if parts and parts[0].strip():
        sections.append(("(preamble)", parts[0]))
    i = 1
    while i < len(parts):
        heading = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        sections.append((heading, body))
        i += 2
    return sections


def _find_matches(text: str, patterns: list[re.Pattern]) -> list[str]:
    """Return the lines (stripped) that match any pattern."""
    hits = []
    for line in text.splitlines():
        if any(p.search(line) for p in patterns):
            hits.append(line.strip())
    return hits


# --- top-level ----------------------------------------------------------


class RuleConflictLinter:
    """Static checker for skill markdown. Stateless, deterministic."""

    def __init__(
        self,
        *,
        description_char_limit: int = 1024,     # Hermes Agent limit
        body_char_limit: int = 6000,            # soft body cap
        require_trivial_carve_out: bool = True,
    ) -> None:
        self.description_char_limit = description_char_limit
        self.body_char_limit = body_char_limit
        self.require_trivial_carve_out = require_trivial_carve_out

    # ---- main entry ---

    def lint(self, skill_md: str) -> list[LintFinding]:
        findings: list[LintFinding] = []
        findings.extend(self._check_frontmatter(skill_md))
        findings.extend(self._check_length(skill_md))
        findings.extend(self._check_rule_conflicts(skill_md))
        return findings

    def has_blocking_findings(self, findings: list[LintFinding]) -> bool:
        return any(f.severity == Severity.HIGH for f in findings)

    # ---- sub-checks ---

    def _check_frontmatter(self, md: str) -> list[LintFinding]:
        """Use PyYAML so block scalars (|, >, folded) are handled correctly."""
        found: list[LintFinding] = []
        if not md.lstrip().startswith("---"):
            found.append(LintFinding(
                kind="missing_frontmatter",
                severity=Severity.HIGH,
                message="SKILL.md must begin with YAML frontmatter delimited by '---'.",
                evidence=[md.splitlines()[0] if md.strip() else "(empty)"],
            ))
            return found

        # Locate frontmatter block
        m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
        if not m:
            found.append(LintFinding(
                kind="unclosed_frontmatter",
                severity=Severity.HIGH,
                message="Frontmatter not closed with a '---' line.",
                evidence=[md[:100]],
            ))
            return found

        fm_raw = m.group(1)
        try:
            fm = yaml.safe_load(fm_raw)
        except yaml.YAMLError as e:
            found.append(LintFinding(
                kind="invalid_yaml",
                severity=Severity.HIGH,
                message=f"Frontmatter is not valid YAML: {e}",
                evidence=[fm_raw[:200]],
            ))
            return found

        if not isinstance(fm, dict):
            found.append(LintFinding(
                kind="frontmatter_not_mapping",
                severity=Severity.HIGH,
                message="Frontmatter must be a YAML mapping.",
                evidence=[str(fm)[:200]],
            ))
            return found

        if "name" not in fm or not fm["name"]:
            found.append(LintFinding(
                kind="missing_name",
                severity=Severity.HIGH,
                message="Frontmatter must include a non-empty 'name' field.",
                evidence=[fm_raw[:200]],
            ))

        desc = fm.get("description")
        if desc is None:
            found.append(LintFinding(
                kind="missing_description",
                severity=Severity.HIGH,
                message="Frontmatter must include a 'description' field.",
                evidence=[fm_raw[:200]],
            ))
        else:
            desc_str = str(desc)
            if len(desc_str) > self.description_char_limit:
                found.append(LintFinding(
                    kind="description_too_long",
                    severity=Severity.HIGH,
                    message=(
                        f"description is {len(desc_str)} chars, "
                        f"exceeds hard limit {self.description_char_limit}. "
                        "Will be truncated silently by Claude Code/Hermes loaders."
                    ),
                    evidence=[desc_str[:120] + ("..." if len(desc_str) > 120 else "")],
                ))

        return found

    def _check_length(self, md: str) -> list[LintFinding]:
        found: list[LintFinding] = []
        body = re.sub(r"^---\n.*?\n---\n", "", md, count=1, flags=re.S)
        if len(body) > self.body_char_limit:
            found.append(LintFinding(
                kind="body_too_long",
                severity=Severity.MEDIUM,
                message=(
                    f"Body is {len(body)} chars (soft cap {self.body_char_limit}). "
                    "Consider moving detail to references/ files."
                ),
                evidence=[f"body_chars={len(body)}"],
            ))
        return found

    def _check_rule_conflicts(self, md: str) -> list[LintFinding]:
        """The core POC-validated check.

        We look for the pattern:
            absolute directive somewhere  +  qualified exception somewhere
        in the same skill without an explicit link between them.
        """
        found: list[LintFinding] = []
        sections = _split_sections(md)

        absolute_hits: list[tuple[str, str]] = []     # (section_heading, line)
        qualifier_hits: list[tuple[str, str]] = []

        for heading, body in sections:
            for line in _find_matches(body, ABSOLUTE_PATTERNS):
                # If the absolute line ITSELF contains an inline carve-out
                # (except/unless/only when/do not apply/for trivial), it's
                # a well-scoped rule, not an unconditional command.
                if any(p.search(line) for p in QUALIFIER_PATTERNS):
                    continue  # self-qualified — don't flag
                absolute_hits.append((heading, line))
            for line in _find_matches(body, QUALIFIER_PATTERNS):
                qualifier_hits.append((heading, line))

        if absolute_hits and qualifier_hits:
            # Cross-compare: does the same topic word appear in both?
            # Simple heuristic: extract content nouns and check overlap. To stay
            # dependency-free, use a word-bag intersection excluding stopwords.
            conflicts = self._pair_overlapping_rules(absolute_hits, qualifier_hits)
            for abs_sec, abs_line, qual_sec, qual_line, shared in conflicts:
                found.append(LintFinding(
                    kind="rule_conflict",
                    severity=Severity.HIGH,
                    message=(
                        "Possible internal rule conflict: an absolute directive "
                        f"({abs_sec!r}) may be overridden by a qualified exception "
                        f"({qual_sec!r}) on shared topic(s): {sorted(shared)}. "
                        "Reconcile by scoping the absolute rule explicitly."
                    ),
                    evidence=[
                        f"ABSOLUTE ({abs_sec}): {abs_line}",
                        f"QUALIFIED ({qual_sec}): {qual_line}",
                    ],
                ))

        # Also flag "Always checklist"-style standalone (empirically the POC killer).
        # English + Chinese topic words: checklist/verify/verification; 清单/验证/核对/检查
        checklist_topic_re = re.compile(
            r"checklist|success criteri|verify|verification|checkmark"
            r"|清单|验证|核对|确认|检查",
            re.I,
        )
        for heading, line in absolute_hits:
            if checklist_topic_re.search(line):
                if self.require_trivial_carve_out:
                    has_topic_carveout = any(
                        checklist_topic_re.search(q_line)
                        for _, q_line in qualifier_hits
                    )
                    if not has_topic_carveout:
                        found.append(LintFinding(
                            kind="absolute_checklist_without_carveout",
                            severity=Severity.HIGH,
                            message=(
                                "An 'always include checklist/verification' rule "
                                "exists without a topic-matched carve-out. A "
                                "generic 'trivial exception' elsewhere does NOT "
                                "cover the checklist rule. This is the POC-2 H04 "
                                "failure mode: trivial requests (rename, typo-fix) "
                                "get ceremonial overhead."
                            ),
                            evidence=[f"{heading}: {line}"],
                        ))

        return found

    # ---- helpers ---

    _STOPWORDS = {
        "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
        "is", "are", "be", "this", "that", "it", "you", "your", "if", "when",
        "then", "should", "not", "no", "all", "any", "each", "every",
        "always", "never", "must", "may", "might", "can", "could", "would",
        "do", "does", "did", "have", "has", "had", "will", "shall", "so",
        "but", "as", "at", "by", "from", "into", "onto", "out", "up", "down",
    }

    @classmethod
    def _content_words(cls, line: str) -> set[str]:
        words = re.findall(r"[A-Za-z_][A-Za-z0-9_\-]{2,}", line.lower())
        return {w for w in words if w not in cls._STOPWORDS}

    @classmethod
    def _pair_overlapping_rules(
        cls,
        absolute_hits: list[tuple[str, str]],
        qualifier_hits: list[tuple[str, str]],
    ) -> list[tuple[str, str, str, str, set[str]]]:
        out = []
        for abs_sec, abs_line in absolute_hits:
            aw = cls._content_words(abs_line)
            for qual_sec, qual_line in qualifier_hits:
                if abs_sec == qual_sec and abs_line == qual_line:
                    continue
                qw = cls._content_words(qual_line)
                shared = aw & qw
                # Require >= 2 shared content words to avoid noise
                if len(shared) >= 2:
                    out.append((abs_sec, abs_line, qual_sec, qual_line, shared))
        # dedupe on (abs_sec, qual_sec) to avoid N^2 noise
        seen = set()
        dedup = []
        for rec in out:
            key = (rec[0], rec[2])
            if key in seen:
                continue
            seen.add(key)
            dedup.append(rec)
        return dedup
