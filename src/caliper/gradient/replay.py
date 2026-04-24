"""Counterfactual Replay — section-level causal ablation.

For each top-level section in the SKILL.md, remove that section and
re-evaluate on the same eval cases. ACE_i = score(full) - score(without_i).

This is the closest we get to "true gradient" without LLM self-attribution.
Reference: Meng et al. 2022 (ROME causal mediation).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class SectionSplit:
    frontmatter: str  # including both `---` fences + newline
    preamble: str  # text between frontmatter end and first heading
    sections: list[tuple[str, str]]  # (heading_line, body_including_trailing_newlines)

    def rebuild(self) -> str:
        parts = [self.frontmatter, self.preamble]
        for h, b in self.sections:
            parts.append(h + "\n" + b)
        return "".join(parts)

    def rebuild_without(self, idx: int) -> str:
        keep = [s for i, s in enumerate(self.sections) if i != idx]
        parts = [self.frontmatter, self.preamble]
        for h, b in keep:
            parts.append(h + "\n" + b)
        return "".join(parts)

    @property
    def section_ids(self) -> list[str]:
        return [h.strip() for h, _ in self.sections]


# ---------- splitter ----------


_HEADING_RE = re.compile(r"^(#{1,3} .+)$", re.MULTILINE)


def split_skill_sections(skill_md: str) -> SectionSplit:
    """Split a SKILL.md into frontmatter + preamble + H1-H3 sections."""
    fm_m = re.match(r"^(---\n.*?\n---\n)", skill_md, re.S)
    if fm_m:
        frontmatter = fm_m.group(1)
        rest = skill_md[fm_m.end() :]
    else:
        frontmatter = ""
        rest = skill_md

    # Find section boundaries via H1-H3 headings
    headings = list(_HEADING_RE.finditer(rest))
    if not headings:
        return SectionSplit(frontmatter=frontmatter, preamble=rest, sections=[])

    preamble = rest[: headings[0].start()]
    sections: list[tuple[str, str]] = []
    for i, m in enumerate(headings):
        heading_line = m.group(1)
        body_start = m.end() + 1  # skip the newline after heading
        body_end = headings[i + 1].start() if i + 1 < len(headings) else len(rest)
        body = rest[body_start:body_end]
        sections.append((heading_line, body))
    return SectionSplit(frontmatter=frontmatter, preamble=preamble, sections=sections)


# ---------- counterfactual ablation ----------


def counterfactual_ablation(
    skill_md: str,
    scorer: Callable[[str], float],
    *,
    baseline_score: float | None = None,
) -> dict[str, float]:
    """For each section, ablate it and measure score drop.

    Returns dict {section_heading: ACE_i} where
        ACE_i = baseline_score - score(skill_without_section_i)

    Positive ACE = section helps (removing it hurts).
    Negative ACE = section hurts (removing it helps).

    Parameters
    ----------
    scorer: callable(skill_md) -> float in [0,1]
    baseline_score: if None, will call `scorer(skill_md)` first.
    """
    split = split_skill_sections(skill_md)
    if not split.sections:
        return {}

    if baseline_score is None:
        baseline_score = scorer(skill_md)

    out: dict[str, float] = {}
    for i, (heading, _) in enumerate(split.sections):
        ablated_md = split.rebuild_without(i)
        s = scorer(ablated_md)
        out[heading.strip()] = float(baseline_score - s)
    return out
