"""TMC-Shapley attribution over skill sections.

Shapley value: fair attribution of a set's value to its parts under
permutation-averaging. TMC (truncated Monte Carlo) by Ghorbani-Zou 2019
keeps sampling cheap by early-stopping when marginal gains vanish.

Property:  sum_i phi_i = v(full) - v(empty)    (efficiency)

Where v(S) = score(skill with only sections in S) and empty = no sections
(only frontmatter + preamble).
"""

from __future__ import annotations

import random
from collections.abc import Callable

from caliper.gradient.replay import split_skill_sections


def _value_of_subset(split, idx_set: frozenset[int], scorer: Callable[[str], float]) -> float:
    """Score the skill containing only sections with indices in idx_set."""
    parts = [split.frontmatter, split.preamble]
    for i, (h, b) in enumerate(split.sections):
        if i in idx_set:
            parts.append(h + "\n" + b)
    return float(scorer("".join(parts)))


def tmc_shapley(
    skill_md: str,
    scorer: Callable[[str], float],
    *,
    num_permutations: int = 50,
    truncation_tolerance: float = 1e-3,
    seed: int = 0,
    cache_subsets: bool = True,
    progress: Callable[[int, int], None] | None = None,
) -> dict[str, float]:
    """Monte Carlo Shapley value per top-level section.

    Algorithm (Castro et al. 2009 + Ghorbani-Zou 2019 truncation):
        phi_i = (1/M) * sum_m [ v(P_m^i ∪ {i}) - v(P_m^i) ]
    where P_m^i = sections preceding i in permutation m.

    TMC truncation: once the marginal gain falls below `truncation_tolerance`
    for the rest of a permutation, treat remaining marginals as 0 (cheap).

    scorer MUST be deterministic or near-deterministic for Shapley to be
    meaningful; use judge caching upstream.

    Returns dict {section_heading: phi_i}. With `cache_subsets=True`, the
    value function is memoized across permutations — trades memory for a
    big speedup (typical 5-10x reduction in LLM calls).
    """
    split = split_skill_sections(skill_md)
    n = len(split.sections)
    if n == 0:
        return {}

    rng = random.Random(seed)
    # value cache keyed by frozenset of indices
    cache: dict[frozenset, float] = {}

    def v(idx_set: frozenset[int]) -> float:
        if cache_subsets and idx_set in cache:
            return cache[idx_set]
        val = _value_of_subset(split, idx_set, scorer)
        if cache_subsets:
            cache[idx_set] = val
        return val

    phi_sum = [0.0] * n
    full_val = v(frozenset(range(n)))

    for m in range(num_permutations):
        perm = list(range(n))
        rng.shuffle(perm)
        prev_val = v(frozenset())
        S: set[int] = set()
        truncated = False
        for idx in perm:
            if truncated:
                # remaining marginals treated as 0
                continue
            S.add(idx)
            cur_val = v(frozenset(S))
            phi_sum[idx] += cur_val - prev_val
            # truncation check
            if abs(full_val - cur_val) < truncation_tolerance:
                truncated = True
            prev_val = cur_val
        if progress:
            progress(m + 1, num_permutations)

    phi = [p / num_permutations for p in phi_sum]
    headings = split.section_ids
    return {h: phi[i] for i, h in enumerate(headings)}
