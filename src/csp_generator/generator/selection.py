"""Minimum-clue-set selection via greedy removal with multi-restart.

Before greedy reduction, a sequence of cap passes trims the pool so the
clue-type distribution lands closer to the canonical Einstein puzzle
(~8 PA, ~4 Adjacency, ~2 AbsolutePosition, ~1 ImmediateLeftOf). Without
these caps the reducer's "keep strong, drop weak" bias collapses output
into a PA + ImmediateLeftOf monoculture — ImmediateLeftOf is strictly
stronger than Adjacency and AbsolutePosition, so every weaker spatial
clue gets stripped as redundant. The caps cut the pool first; greedy
then has no choice but to lean on the weaker types for coverage.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable

from csp_generator.models import (
    AbsolutePosition,
    Adjacency,
    Clue,
    Conditional,
    Disjunction,
    ImmediateLeftOf,
    NegativeAssociation,
    PositiveAssociation,
    Puzzle,
    RelativePosition,
    Solution,
    Theme,
)
from csp_generator.solver.ortools_solver import is_uniquely_solvable

# Lower value → try to remove first (cheapest / most redundant clues).
# PA stays last (the most informative single clue type). The three spatial
# survivors — Adjacency, AbsolutePosition, ImmediateLeftOf — sit close
# together so the reducer doesn't strip one type wholesale in favor of
# another; combined with the per-type caps below this preserves a mixed
# spatial vocabulary instead of collapsing to whichever type is strongest.
# RelativePosition and NegativeAssociation are intentionally lowest: the
# Einstein puzzle uses neither (NA is also currently absent from the
# enumerator), so they're stripped before any spatial type the reducer
# wants to keep.
_REMOVAL_PRIORITY: dict[str, int] = {
    "relative_position": 0,
    "negative_association": 1,
    "adjacency": 2,
    "absolute_position": 3,
    "immediate_left_of": 4,
    "positive_association": 5,
}


def _priority_shuffle(pool: list[Clue], rng: random.Random) -> list[Clue]:
    """Sort by removal priority; break ties randomly so each restart is distinct."""
    return sorted(pool, key=lambda c: (_REMOVAL_PRIORITY.get(c.type, 99), rng.random()))


def _pa_owner(clue: PositiveAssociation, solution: Solution) -> int:
    """The position a PA clue anchors. Both sides agree by construction."""
    return solution.position_of(clue.category_a, clue.value_a)


def _greedy_reduce(
    pool: list[Clue],
    solution: Solution,
    theme: Theme,
    rng: random.Random,
    protect_ref: tuple[str, str] | None = None,
) -> list[Clue]:
    """Single greedy pass: order pool by removal priority, try removing each clue.

    A clue is dropped permanently if the remaining set still produces a
    uniquely solvable puzzle and (if `protect_ref` is set) still mentions
    that `(category, value)` reference somewhere — keeps the answer entity's
    name from being orphaned.
    """
    current = _priority_shuffle(pool, rng)
    for clue in list(current):
        candidate = [c for c in current if c is not clue]
        if protect_ref is not None and not any(clue_references(c, *protect_ref) for c in candidate):
            continue
        probe = Puzzle(
            id="__probe__",
            theme_id=theme.id,
            size=theme.size,
            clues=candidate,
        )
        if is_uniquely_solvable(probe, theme):
            current = candidate
    return current


def _cap_category_pas(
    current: list[Clue],
    theme: Theme,
    rng: random.Random,
    question_category: str,
    max_pa: int,
    protect_ref: tuple[str, str] | None = None,
) -> list[Clue]:
    """Strip PA clues touching `question_category` until the count is <= max_pa.

    Destacking caps PAs *per entity*; this caps PAs *per category*. On small
    grids (4x4) the per-entity cap can be satisfied while three of four values
    in the question category are still directly PA-pinned, making the answer
    fall out by trivial elimination. Capping at `size - 2` forces at least two
    values in that category to be reached via positional/adjacency/elimination
    instead of direct identity — which forces the spatial clues to fire.

    Best-effort with the same semantics as `_cap_clue_count` (uniqueness
    preserved, `protect_ref` honored, cap may go unmet if every touching
    PA is load-bearing).
    """
    return _cap_clue_count(
        current,
        theme,
        rng,
        predicate=lambda c: isinstance(c, PositiveAssociation)
        and (c.category_a == question_category or c.category_b == question_category),
        max_count=max_pa,
        protect_ref=protect_ref,
    )


def _cap_clue_count(
    current: list[Clue],
    theme: Theme,
    rng: random.Random,
    predicate: Callable[[Clue], bool],
    max_count: int,
    protect_ref: tuple[str, str] | None = None,
) -> list[Clue]:
    """Strip clues matching `predicate` until at most `max_count` remain.

    Each removal must preserve uniqueness and (if `protect_ref` is set) keep
    the protected `(category, value)` reference alive somewhere in the set.
    Best-effort: if every matching clue is load-bearing the cap can go unmet.

    Used to enforce Einstein-style type ratios: caps ImmediateLeftOf at 1
    and AbsolutePosition at 2 before greedy reduction, so the reducer is
    forced to lean on Adjacency and PA for the remaining spatial work
    instead of swapping everything for the strongest available type.
    """
    while True:
        matching = [c for c in current if predicate(c)]
        if len(matching) <= max_count:
            return current
        ordered = list(matching)
        rng.shuffle(ordered)

        removed = False
        for clue in ordered:
            candidate = [c for c in current if c is not clue]
            if protect_ref is not None and not any(
                clue_references(c, *protect_ref) for c in candidate
            ):
                continue
            probe = Puzzle(
                id="__probe__",
                theme_id=theme.id,
                size=theme.size,
                clues=candidate,
            )
            if is_uniquely_solvable(probe, theme):
                current = candidate
                removed = True
                break
        if not removed:
            return current


def _destack_pa(
    current: list[Clue],
    solution: Solution,
    theme: Theme,
    rng: random.Random,
    max_pa_per_entity: int = 2,
    protect_ref: tuple[str, str] | None = None,
) -> list[Clue]:
    """Strip PA clues from positions pinned by more than `max_pa_per_entity` of them.

    Each removal must preserve uniqueness and (if `protect_ref` is set) keep
    the protected `(category, value)` reference alive somewhere in the set.
    Saturation is recomputed after every successful removal because the
    surplus shrinks as we strip.
    """
    while True:
        pa_clues = [c for c in current if isinstance(c, PositiveAssociation)]
        saturation = Counter(_pa_owner(c, solution) for c in pa_clues)
        targets = [c for c in pa_clues if saturation[_pa_owner(c, solution)] > max_pa_per_entity]
        if not targets:
            return current
        # Try the most-saturated entity's PAs first; randomize ties so multi-restart
        # explores different removal orders.
        targets.sort(key=lambda c: (-saturation[_pa_owner(c, solution)], rng.random()))

        removed = False
        for clue in targets:
            candidate = [c for c in current if c is not clue]
            if protect_ref is not None and not any(
                clue_references(c, *protect_ref) for c in candidate
            ):
                continue
            probe = Puzzle(
                id="__probe__",
                theme_id=theme.id,
                size=theme.size,
                clues=candidate,
            )
            if is_uniquely_solvable(probe, theme):
                current = candidate
                removed = True
                break  # recompute saturation and continue
        if not removed:
            return current


def select_minimum_clues(
    pool: list[Clue],
    solution: Solution,
    theme: Theme,
    rng: random.Random,
    n_restarts: int = 5,
    max_pa_per_entity: int = 2,
    max_immediate_left_of: int = 1,
    max_absolute_position: int = 2,
    protect_ref: tuple[str, str] | None = None,
    question_category: str | None = None,
) -> list[Clue]:
    """Return a near-minimum subset of `pool` that still uniquely solves to `solution`.

    Five passes, in order:
      1. `_cap_category_pas` — caps PA clues touching the question category
         at `theme.size - 2` (so at least two values in that category must
         be deduced spatially, not via direct identity).
      2. `_destack_pa` — caps PA clues per entity at `max_pa_per_entity`.
      3. `_cap_clue_count` on ImmediateLeftOf at `max_immediate_left_of`
         (default 1, matching Einstein's puzzle exactly).
      4. `_cap_clue_count` on AbsolutePosition at `max_absolute_position`
         (default 2, matching Einstein).
      5. `_greedy_reduce` repeated `n_restarts` times — strips remaining
         redundancy.

    All passes respect `protect_ref` so the answer-bearing entity's name is
    never orphaned. Type caps run on the full pool — they trim *upper*
    bounds before greedy gets a shot. Without the caps, greedy strips
    weaker spatial types (Adjacency, AbsolutePosition) whenever a stronger
    ImmediateLeftOf can stand in, which collapses the output to a
    PA + ImmediateLeftOf monoculture. Adjacency is intentionally left
    uncapped — once ImmediateLeftOf is rationed to 1, Adjacency naturally
    picks up the spatial slack at roughly Einstein-proportional rates.
    """
    if n_restarts < 1:
        raise ValueError(f"n_restarts must be >= 1, got {n_restarts}")

    if question_category is not None:
        pool = _cap_category_pas(
            pool,
            theme,
            rng,
            question_category=question_category,
            max_pa=max(0, theme.size - 2),
            protect_ref=protect_ref,
        )
    pool = _destack_pa(
        pool,
        solution,
        theme,
        rng,
        max_pa_per_entity=max_pa_per_entity,
        protect_ref=protect_ref,
    )
    pool = _cap_clue_count(
        pool,
        theme,
        rng,
        predicate=lambda c: isinstance(c, ImmediateLeftOf),
        max_count=max_immediate_left_of,
        protect_ref=protect_ref,
    )
    pool = _cap_clue_count(
        pool,
        theme,
        rng,
        predicate=lambda c: isinstance(c, AbsolutePosition),
        max_count=max_absolute_position,
        protect_ref=protect_ref,
    )
    best = _greedy_reduce(pool, solution, theme, rng, protect_ref=protect_ref)
    for _ in range(n_restarts - 1):
        candidate = _greedy_reduce(best, solution, theme, rng, protect_ref=protect_ref)
        if len(candidate) < len(best):
            best = candidate
    return best


# ---------------------------------------------------------------------------
# Reference probe — part of the module's public contract: the pipeline shares
# it to enforce answer suppression, and the quality tests use it directly.
# ---------------------------------------------------------------------------


def clue_references(clue: Clue, category: str, value: str) -> bool:
    """True if `(category, value)` appears anywhere in the clue's fields."""
    target = (category, value)
    if isinstance(
        clue,
        PositiveAssociation | NegativeAssociation | Adjacency | RelativePosition | ImmediateLeftOf,
    ):
        return target in {(clue.category_a, clue.value_a), (clue.category_b, clue.value_b)}
    if isinstance(clue, AbsolutePosition):
        return (clue.category, clue.value) == target
    if isinstance(clue, Disjunction):
        return (clue.category_a, clue.value_a) == target or target in clue.options
    if isinstance(clue, Conditional):
        return target in {
            (clue.if_category_a, clue.if_value_a),
            (clue.if_category_b, clue.if_value_b),
            (clue.then_category_a, clue.then_value_a),
            (clue.then_category_b, clue.then_value_b),
        }
    return False


__all__ = ["clue_references", "select_minimum_clues"]
