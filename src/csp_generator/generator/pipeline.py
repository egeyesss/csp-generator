"""End-to-end puzzle generation pipeline."""

from __future__ import annotations

import random
import uuid

from csp_generator.analytics.difficulty import composite_difficulty
from csp_generator.analytics.variety import clue_variety
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
from csp_generator.solver.propagator import trace


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
    min_difficulty: float | None = None,
    max_retries: int = 10,
) -> Puzzle:
    """Generate a uniquely-solvable puzzle for `theme`.

    Steps:
    1. Draw a random valid solution.
    2. Enumerate every clue that's true under that solution, excluding
       NegativeAssociation and any PA clue that directly states the
       theme's question_target answer (so the answer stays deducible,
       not given).
    3. Greedily strip redundant clues until the set is near-minimal.

    Returns a Puzzle with the solution, question, and full metrics attached
    (clue count plus the tracer's deduction/branching metrics, clue variety,
    and the composite difficulty score).

    If `min_difficulty` is provided, the loop retries up to `max_retries`
    times until a puzzle's `composite_difficulty` clears the floor. Falls
    back to the highest-difficulty attempt if none do — never returns
    `None` or raises on unreachable floors.
    """
    if rng is None:
        rng = random.Random()

    best: Puzzle | None = None
    attempts = max_retries if min_difficulty is not None else 1
    for _ in range(attempts):
        puzzle = _generate_once(theme, rng, n_restarts)
        if min_difficulty is None or _difficulty(puzzle) >= min_difficulty:
            return puzzle
        if best is None or _difficulty(puzzle) > _difficulty(best):
            best = puzzle
    assert best is not None  # min_difficulty is not None ⇒ attempts >= 1 ⇒ best set
    return best


def _difficulty(puzzle: Puzzle) -> float:
    """Composite difficulty as a plain float, defaulting to -inf if unset."""
    if puzzle.metrics is None or puzzle.metrics.composite_difficulty is None:
        return float("-inf")
    return puzzle.metrics.composite_difficulty


def _generate_once(theme: Theme, rng: random.Random, n_restarts: int) -> Puzzle:
    qt = theme.question_target
    solution = generate_solution(theme, rng)
    pool: list[Clue] = [
        c
        for c in enumerate_valid_clues(solution, theme)
        if not isinstance(c, NegativeAssociation) and (qt is None or not _is_direct_answer(c, qt))
    ]

    # Keep the answer-bearing entity's name in at least one clue so the player
    # never has to "guess Ana" purely from elimination over the theme's roster.
    protect_ref: tuple[str, str] | None = None
    if qt is not None and "name" in theme.categories:
        qt_cat, qt_val = qt
        answer_pos = solution.position_of(qt_cat, qt_val)
        protect_ref = ("name", solution.value_at("name", answer_pos))

    clues = select_minimum_clues(
        pool, solution, theme, rng, n_restarts=n_restarts, protect_ref=protect_ref
    )

    puzzle = Puzzle(
        id=str(uuid.uuid4()),
        theme_id=theme.id,
        size=theme.size,
        clues=clues,
        solution=solution,
        question=qt,
    )

    result = trace(puzzle, theme)
    variety = clue_variety(clues)
    metrics = GenerationMetrics(
        clue_count=len(clues),
        deduction_depth=result.deduction_depth,
        hypothesis_depth=result.hypothesis_depth,
        branching_factor=result.branching_factor,
        clue_variety=variety,
        composite_difficulty=composite_difficulty(
            deduction_depth=result.deduction_depth,
            hypothesis_depth=result.hypothesis_depth,
            branching_factor=result.branching_factor,
            clue_count=len(clues),
            clue_variety=variety,
            size=theme.size,
        ),
    )
    return puzzle.model_copy(update={"metrics": metrics})


__all__ = ["generate"]
