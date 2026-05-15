"""End-to-end puzzle generation pipeline."""

from __future__ import annotations

import random
import uuid

from csp_generator.clues.enumerator import enumerate_valid_clues
from csp_generator.generator.selection import select_minimum_clues
from csp_generator.generator.solution import generate_solution
from csp_generator.models import GenerationMetrics, Puzzle, Theme


def generate(
    theme: Theme,
    rng: random.Random | None = None,
    n_restarts: int = 5,
) -> Puzzle:
    """Generate a uniquely-solvable puzzle for `theme`.

    Steps:
    1. Draw a random valid solution.
    2. Enumerate every clue that's true under that solution.
    3. Greedily strip redundant clues until the set is near-minimal.

    Returns a Puzzle with the solution and clue_count metric attached.
    `n_restarts` controls how many greedy shuffle-passes the selector runs;
    more passes means a smaller (but not provably optimal) clue set.
    """
    if rng is None:
        rng = random.Random()
    solution = generate_solution(theme, rng)
    pool = enumerate_valid_clues(solution, theme)
    clues = select_minimum_clues(pool, solution, theme, rng, n_restarts=n_restarts)
    return Puzzle(
        id=str(uuid.uuid4()),
        theme_id=theme.id,
        size=theme.size,
        clues=clues,
        solution=solution,
        metrics=GenerationMetrics(clue_count=len(clues)),
    )


__all__ = ["generate"]
