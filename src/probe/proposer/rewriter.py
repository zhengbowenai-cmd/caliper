"""Naive LLM rewriter — placeholder for GEPA/Shapley.

Takes the current champion + structured feedback (linter findings, judge
critiques on lowest-scoring cases) and asks an LLM to rewrite the
SKILL.md. Respects hard constraints: description length, linter HIGH
findings reported back to the model.

This is intentionally simple. When we implement Counterfactual Shapley
the rewriter stays the same — only its INPUT changes (from "judge
feedback" to "Shapley-weighted per-section gradient"). The rewriter
interface is the stable seam.
"""
from __future__ import annotations

from dataclasses import dataclass

from probe.proposer.linter import LintFinding
from probe.runtime.llm import ChatMessage, LLMClient


REWRITE_PROMPT = """You are improving a Claude Code / Anthropic-style SKILL.md.

Current skill:
<<<BEGIN SKILL.md
{skill_md}
END SKILL.md>>>

Structured feedback (these MUST be addressed):

Linter HIGH findings:
{lint_bullets}

Worst-scoring judge critiques (score → critique):
{judge_bullets}

Hard constraints (violating any = rejection):
- Description ≤ {desc_limit} characters (Claude Code / Hermes hard cap)
- Body ≤ {body_limit} characters (soft cap; move detail to references/ if needed)
- NO "always/must/never X" rules unless paired with an explicit topic-matched
  exception. Specifically: if you add "always include a checklist/verification",
  you MUST also state "except for trivial rename/typo/literal-substitution tasks"
  in the same breath.
- Keep YAML frontmatter (---\\nname: ...\\ndescription: ...\\n---)

Output ONLY the revised SKILL.md — no preamble, no explanation, no code fences.
Start directly with "---" for the frontmatter.
"""


@dataclass
class NaiveRewriter:
    """Single-LLM rewriter. Stateless; one call = one candidate."""
    llm: LLMClient
    description_char_limit: int = 1024
    body_char_limit: int = 6000
    temperature: float = 0.5
    max_tokens: int = 4000

    def propose(
        self,
        current_skill_md: str,
        lint_findings: list[LintFinding],
        judge_critiques: list[tuple[float, str]],  # (score, critique)
    ) -> str:
        lint_bullets = "\n".join(
            f"- [{f.severity.value.upper()}] {f.kind}: {f.message}"
            for f in lint_findings if f.severity.value == "high"
        ) or "  (none)"

        # sort by lowest score first, take top 6
        sorted_critiques = sorted(judge_critiques, key=lambda x: x[0])[:6]
        judge_bullets = "\n".join(
            f"- score={s:.2f}: {c.strip()[:300]}"
            for s, c in sorted_critiques
        ) or "  (no critiques provided)"

        prompt = REWRITE_PROMPT.format(
            skill_md=current_skill_md,
            lint_bullets=lint_bullets,
            judge_bullets=judge_bullets,
            desc_limit=self.description_char_limit,
            body_limit=self.body_char_limit,
        )

        response = self.llm.chat(
            [ChatMessage(role="user", content=prompt)],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        return _strip_code_fences(response).strip()


def _strip_code_fences(text: str) -> str:
    """Strip any markdown fences the LLM may add despite instructions."""
    t = text.strip()
    if t.startswith("```"):
        # find first newline, drop
        nl = t.find("\n")
        if nl >= 0:
            t = t[nl + 1:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()
