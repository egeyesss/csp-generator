"""End-to-end puzzle generation pipeline."""

from __future__ import annotations

import random
import uuid

from csp_generator.clues.enumerator import enumerate_valid_clues
from csp_generator.generator.selection import select_minimum_clues
from csp_generator.generator.solution import generate_solution
from csp_generator.models import (
    Clue,
    GenerationMetrics,
    NegativeAssociation,
    PositiveAssociation,
    Puzzle,
    Theme,
)


def _is_direct_answer(clue: Clue, question_target: tuple[str, str]) -> bool:
    """True if this PA clue directly states the question answer."""
    if not isinstance(clue, PositiveAssociation):
        return False
    qt_cat, qt_val = question_target
    return (clue.category_a == qt_cat and clue.value_a == qt_val) or (
        clue.category_b == qt_cat and clue.value_b == qt_val
    )


def generate(
    theme: Theme,
    rng: random.Random | None = None,
    n_restarts: int = 10,
) -> Puzzle:
    """Generate a uniquely-solvable puzzle for `theme`.

    Steps:
    1. Draw a random valid solution.
    2. Enumerate every clue that's true under that solution, excluding
       NegativeAssociation and any PA clue that directly states the
       theme's question_target answer (so the answer stays deducible,
       not given).
    3. Greedily strip redundant clues until the set is near-minimal.

    Returns a Puzzle with the solution, question, and clue_count attached.
    """
    if rng is None:
        rng = random.Random()
    qt = theme.question_target
    solution = generate_solution(theme, rng)
    pool: list[Clue] = [
        c
        for c in enumerate_valid_clues(solution, theme)
        if not isinstance(c, NegativeAssociation) and (qt is None or not _is_direct_answer(c, qt))
    ]
    clues = select_minimum_clues(pool, solution, theme, rng, n_restarts=n_restarts)
    return Puzzle(
        id=str(uuid.uuid4()),
        theme_id=theme.id,
        size=theme.size,
        clues=clues,
        solution=solution,
        question=qt,
        metrics=GenerationMetrics(clue_count=len(clues)),
    )


__all__ = ["generate"]
