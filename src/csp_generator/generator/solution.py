"""Random valid solution generation."""

from __future__ import annotations

import random

from csp_generator.models import Solution, Theme


def generate_solution(theme: Theme, rng: random.Random | None = None) -> Solution:
    """Return a random valid solution for `theme`.

    Each attribute category is independently shuffled, so every position gets
    exactly one value per category (AllDifferent is satisfied by construction).
    """
    if rng is None:
        rng = random.Random()
    assignments: dict[str, list[str]] = {}
    for category, values in theme.attributes.items():
        pool = list(values)
        rng.shuffle(pool)
        assignments[category] = pool
    return Solution(theme_id=theme.id, assignments=assignments)


__all__ = ["generate_solution"]
