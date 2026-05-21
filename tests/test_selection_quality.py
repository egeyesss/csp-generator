"""Structural quality invariants on generated clue sets.

These tests don't just check uniqueness — they check the *shape* of the clue
set we're shipping to players. Two invariants matter for puzzle "feel":

1. **PA distribution.** No single entity should be over-pinned by direct
   PositiveAssociation clues. When that happens the puzzle collapses into
   local pairing-stacks rather than the cross-category web that makes
   Einstein-style puzzles satisfying.
2. **Answer grounding.** The entity holding the question_target answer must
   appear by name in at least one surviving clue (when the theme has a
   `name` category). Otherwise the answer is reachable only by elimination
   over the theme's roster, which feels arbitrary to a player.
"""

from __future__ import annotations

import random
from collections import Counter

import pytest

from csp_generator.generator.pipeline import generate
from csp_generator.models import (
    AbsolutePosition,
    ImmediateLeftOf,
    PositiveAssociation,
    Solution,
    Theme,
)
from csp_generator.themes.loader import load_theme

_MAX_PA_PER_ENTITY = 2


def _pa_count_per_position(clues: list, solution: Solution) -> dict[int, int]:
    """How many PA clues anchor each position in the grid."""
    counts: Counter[int] = Counter()
    for c in clues:
        if isinstance(c, PositiveAssociation):
            counts[solution.position_of(c.category_a, c.value_a)] += 1
    return dict(counts)


@pytest.fixture(scope="module")
def office() -> Theme:
    return load_theme("office")


@pytest.fixture(scope="module")
def dorm() -> Theme:
    return load_theme("dorm")


# ---------------------------------------------------------------------------
# PA destacking
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_no_entity_oversaturated_with_pa_clues(office: Theme, seed: int) -> None:
    """No position in the solution grid should be pinned by more than 2 PAs."""
    puzzle = generate(office, rng=random.Random(seed), n_restarts=3)
    assert puzzle.solution is not None
    counts = _pa_count_per_position(puzzle.clues, puzzle.solution)
    over = {pos: n for pos, n in counts.items() if n > _MAX_PA_PER_ENTITY}
    assert not over, (
        f"office seed={seed}: positions over-pinned by PA clues: {over} "
        f"(full distribution: {counts})"
    )


@pytest.mark.parametrize("seed", [0, 1, 7])
def test_pa_destacking_works_on_dorm_too(dorm: Theme, seed: int) -> None:
    puzzle = generate(dorm, rng=random.Random(seed), n_restarts=3)
    assert puzzle.solution is not None
    counts = _pa_count_per_position(puzzle.clues, puzzle.solution)
    over = {pos: n for pos, n in counts.items() if n > _MAX_PA_PER_ENTITY}
    assert not over, f"dorm seed={seed}: over-pinned: {over} (full: {counts})"


# ---------------------------------------------------------------------------
# Answer grounding
# ---------------------------------------------------------------------------


def _clue_mentions(clue, category: str, value: str) -> bool:
    """True iff `(category, value)` shows up textually in the clue."""
    from csp_generator.generator.selection import _references  # tested separately

    return _references(clue, category, value)


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_answer_entity_is_named_in_at_least_one_clue(office: Theme, seed: int) -> None:
    """If the theme has a `name` category, the answer entity's name must appear."""
    puzzle = generate(office, rng=random.Random(seed), n_restarts=3)
    assert puzzle.solution is not None
    assert puzzle.question is not None
    qt_cat, qt_val = puzzle.question
    answer_pos = puzzle.solution.position_of(qt_cat, qt_val)
    answer_name = puzzle.solution.value_at("name", answer_pos)
    grounded = any(_clue_mentions(c, "name", answer_name) for c in puzzle.clues)
    assert grounded, (
        f"office seed={seed}: answer entity {answer_name!r} (at pos {answer_pos}) "
        f"is never mentioned in any clue"
    )


@pytest.mark.parametrize("seed", [0, 3, 9])
def test_answer_grounded_in_restaurant_theme(seed: int) -> None:
    theme = load_theme("restaurant")
    puzzle = generate(theme, rng=random.Random(seed), n_restarts=3)
    assert puzzle.solution is not None
    assert puzzle.question is not None
    qt_cat, qt_val = puzzle.question
    answer_pos = puzzle.solution.position_of(qt_cat, qt_val)
    answer_name = puzzle.solution.value_at("name", answer_pos)
    grounded = any(_clue_mentions(c, "name", answer_name) for c in puzzle.clues)
    assert grounded, f"restaurant seed={seed}: {answer_name!r} never mentioned"


# ---------------------------------------------------------------------------
# Answer-category PA cap
#
# At small grid sizes, destacking's per-entity cap doesn't prevent the puzzle
# from collapsing into trivial elimination — if N-1 values in the question's
# category are PA-pinned to other attributes, the Nth (the answer) is forced
# without any spatial reasoning. We cap PA clues touching the question's
# category at `size - 2`, so at least two values must be reached via
# positional/adjacency/elimination.
# ---------------------------------------------------------------------------


def _pa_touches_category(clue, category: str) -> bool:
    return isinstance(clue, PositiveAssociation) and (
        clue.category_a == category or clue.category_b == category
    )


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_question_category_not_overpinned_4x4(seed: int) -> None:
    """4x4 restaurant: PA clues touching `dessert` must be <= size - 2 = 2."""
    theme = load_theme("restaurant")
    puzzle = generate(theme, rng=random.Random(seed), n_restarts=3)
    assert puzzle.question is not None
    qt_cat, _ = puzzle.question
    pa_on_qt = sum(1 for c in puzzle.clues if _pa_touches_category(c, qt_cat))
    cap = theme.size - 2
    assert (
        pa_on_qt <= cap
    ), f"restaurant seed={seed}: {pa_on_qt} PAs touch question category {qt_cat!r}, cap is {cap}"


@pytest.mark.parametrize("seed", [0, 1, 7, 42])
def test_question_category_not_overpinned_5x5(seed: int) -> None:
    """5x5 office: PA clues touching `role` must be <= size - 2 = 3."""
    theme = load_theme("office")
    puzzle = generate(theme, rng=random.Random(seed), n_restarts=3)
    assert puzzle.question is not None
    qt_cat, _ = puzzle.question
    pa_on_qt = sum(1 for c in puzzle.clues if _pa_touches_category(c, qt_cat))
    cap = theme.size - 2
    assert (
        pa_on_qt <= cap
    ), f"office seed={seed}: {pa_on_qt} PAs touch question category {qt_cat!r}, cap is {cap}"


# ---------------------------------------------------------------------------
# Type caps — mirror Einstein's clue-type ratios
#
# Einstein's puzzle has exactly 1 ImmediateLeftOf and 2 AbsolutePosition out
# of 15 clues. Without per-type caps, ImmediateLeftOf is strictly stronger
# than Adjacency and AbsolutePosition, so greedy reduction strips the weaker
# spatial types and collapses the puzzle into a PA + ImmediateLeftOf
# monoculture. The caps keep the spatial vocabulary mixed.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme_id", ["classic_houses", "office", "dorm", "restaurant"])
@pytest.mark.parametrize("seed", [0, 1, 7])
def test_immediate_left_of_capped_at_one(theme_id: str, seed: int) -> None:
    """At most 1 ImmediateLeftOf per puzzle on every theme — matches Einstein."""
    theme = load_theme(theme_id)
    puzzle = generate(theme, rng=random.Random(seed), n_restarts=3)
    count = sum(1 for c in puzzle.clues if isinstance(c, ImmediateLeftOf))
    assert count <= 1, f"{theme_id} seed={seed}: {count} ImmediateLeftOf clues, cap is 1"


@pytest.mark.parametrize("theme_id", ["classic_houses", "office", "dorm", "restaurant"])
@pytest.mark.parametrize("seed", [0, 1, 7])
def test_absolute_position_capped_at_two(theme_id: str, seed: int) -> None:
    """At most 2 AbsolutePosition clues per puzzle — matches Einstein."""
    theme = load_theme(theme_id)
    puzzle = generate(theme, rng=random.Random(seed), n_restarts=3)
    count = sum(1 for c in puzzle.clues if isinstance(c, AbsolutePosition))
    assert count <= 2, f"{theme_id} seed={seed}: {count} AbsolutePosition clues, cap is 2"


@pytest.mark.parametrize("theme_id", ["classic_houses", "restaurant"])
def test_spatial_vocabulary_is_mixed(theme_id: str) -> None:
    """Across a batch, all three capped types (ILo, AbsPos, Adj) should appear.

    Tests the *aggregate* — a single puzzle may miss one type, but generating
    a handful with different seeds should hit at least one occurrence of each.
    Pre-cap behavior was 0 Adj and 0 AbsPos across hundreds of puzzles.
    """
    theme = load_theme(theme_id)
    type_counts: Counter[str] = Counter()
    for seed in range(10):
        puzzle = generate(theme, rng=random.Random(seed), n_restarts=3)
        type_counts.update(c.type for c in puzzle.clues)
    for clue_type in ("adjacency", "absolute_position", "immediate_left_of"):
        assert type_counts[clue_type] > 0, (
            f"{theme_id}: {clue_type} never appears across 10 seeds "
            f"(distribution: {dict(type_counts)})"
        )
