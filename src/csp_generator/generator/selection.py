"""Minimum-clue-set selection via greedy removal with multi-restart."""

from __future__ import annotations

import random

from csp_generator.models import Clue, Puzzle, Solution, Theme
from csp_generator.solver.ortools_solver import is_uniquely_solvable

# Lower value → try to remove first (cheapest / most redundant clues).
# RelPos and AbsPos are the most numerous; PA is the most informative and
# hardest to drop, so we leave it for last. This ordering makes the greedy
# pass strip redundant positional clues while PA clues are still present to
# cover them — the result skews toward a PA-heavy, RelPos-light clue set
# that reads like a natural zebra puzzle.
_REMOVAL_PRIORITY: dict[str, int] = {
    "relative_position": 0,
    "absolute_position": 1,
    "adjacency": 2,
    "negative_association": 3,
    "positive_association": 4,
}


def _priority_shuffle(pool: list[Clue], rng: random.Random) -> list[Clue]:
    """Sort by removal priority; break ties randomly so each restart is distinct."""
    return sorted(pool, key=lambda c: (_REMOVAL_PRIORITY.get(c.type, 99), rng.random()))


def _greedy_reduce(
    pool: list[Clue],
    solution: Solution,
    theme: Theme,
    rng: random.Random,
) -> list[Clue]:
    """Single greedy pass: order pool by removal priority, try removing each clue.

    A clue is dropped permanently if the remaining set still produces a
    uniquely solvable puzzle. Returns the reduced clue list.
    """
    current = _priority_shuffle(pool, rng)
    for clue in list(current):
        candidate = [c for c in current if c is not clue]
        probe = Puzzle(
            id="__probe__",
            theme_id=theme.id,
            size=theme.size,
            clues=candidate,
        )
        if is_uniquely_solvable(probe, theme):
            current = candidate
    return current


def select_minimum_clues(
    pool: list[Clue],
    solution: Solution,
    theme: Theme,
    rng: random.Random,
    n_restarts: int = 5,
) -> list[Clue]:
    """Return a near-minimum subset of `pool` that still uniquely solves to `solution`.

    Runs `n_restarts` greedy passes, each with a different shuffle of the current
    best result. The first pass starts from the full pool; subsequent passes start
    from the previous best — this keeps later passes cheap since most redundancy
    was already stripped.
    """
    if n_restarts < 1:
        raise ValueError(f"n_restarts must be >= 1, got {n_restarts}")

    best = _greedy_reduce(pool, solution, theme, rng)
    for _ in range(n_restarts - 1):
        candidate = _greedy_reduce(best, solution, theme, rng)
        if len(candidate) < len(best):
            best = candidate
    return best


__all__ = ["select_minimum_clues"]
