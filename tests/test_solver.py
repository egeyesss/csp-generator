"""Solver behavior on hand-written 5x5 puzzles.

The headline case is the classic zebra (Einstein) riddle: a 15-clue puzzle
known to have exactly one solution. We encode it as a `Puzzle` against the
classic_houses theme and check that:

  1. `solve` returns the documented unique assignment.
  2. `is_uniquely_solvable` returns True.
  3. Removing a load-bearing clue makes uniqueness fail.
"""

from __future__ import annotations

from csp_generator.models import (
    AbsolutePosition,
    Adjacency,
    Clue,
    ImmediateLeftOf,
    PositiveAssociation,
    Puzzle,
    RelativePosition,
)
from csp_generator.solver import count_solutions, is_uniquely_solvable, solve
from csp_generator.themes import load_theme


def _pa(ca: str, va: str, cb: str, vb: str) -> PositiveAssociation:
    return PositiveAssociation(category_a=ca, value_a=va, category_b=cb, value_b=vb)


def _adj(ca: str, va: str, cb: str, vb: str) -> Adjacency:
    return Adjacency(category_a=ca, value_a=va, category_b=cb, value_b=vb)


def _einstein_clues() -> list[Clue]:
    """The canonical 15 clues of the zebra puzzle.

    Clue 6 ("green house is immediately to the right of the ivory house") is
    expressed as the conjunction of an Adjacency and a RelativePosition: the
    ivory and green houses are adjacent AND ivory is somewhere to the left of
    green, which together forces them to be consecutive in that order.
    """
    return [
        _pa("nationality", "Englishman", "color", "red"),  # 2
        _pa("nationality", "Spaniard", "pet", "dog"),  # 3
        _pa("drink", "coffee", "color", "green"),  # 4
        _pa("nationality", "Ukrainian", "drink", "tea"),  # 5
        # 6: green immediately to the right of ivory
        _adj("color", "ivory", "color", "green"),
        RelativePosition(category_a="color", value_a="ivory", category_b="color", value_b="green"),
        _pa("cigarette", "Old Gold", "pet", "snails"),  # 7
        _pa("cigarette", "Kools", "color", "yellow"),  # 8
        AbsolutePosition(category="drink", value="milk", position=2),  # 9
        AbsolutePosition(category="nationality", value="Norwegian", position=0),  # 10
        _adj("cigarette", "Chesterfields", "pet", "fox"),  # 11
        _adj("cigarette", "Kools", "pet", "horse"),  # 12
        _pa("cigarette", "Lucky Strike", "drink", "orange juice"),  # 13
        _pa("nationality", "Japanese", "cigarette", "Parliaments"),  # 14
        _adj("nationality", "Norwegian", "color", "blue"),  # 15
    ]


def _einstein_puzzle(clues: list[Clue] | None = None) -> Puzzle:
    return Puzzle(
        id="einstein-classic",
        theme_id="classic_houses",
        size=5,
        clues=clues if clues is not None else _einstein_clues(),
    )


# The documented unique solution to the zebra puzzle.
_EXPECTED_SOLUTION = {
    "color": ["yellow", "blue", "red", "ivory", "green"],
    "nationality": ["Norwegian", "Ukrainian", "Englishman", "Spaniard", "Japanese"],
    "drink": ["water", "tea", "milk", "orange juice", "coffee"],
    "pet": ["fox", "horse", "snails", "dog", "zebra"],
    "cigarette": ["Kools", "Chesterfields", "Old Gold", "Lucky Strike", "Parliaments"],
}


def test_einstein_riddle_has_known_solution() -> None:
    theme = load_theme("classic_houses")
    sol = solve(_einstein_puzzle(), theme)
    assert sol is not None
    assert sol.assignments == _EXPECTED_SOLUTION


def test_einstein_riddle_is_uniquely_solvable() -> None:
    theme = load_theme("classic_houses")
    assert is_uniquely_solvable(_einstein_puzzle(), theme) is True


def test_removing_load_bearing_clue_breaks_uniqueness() -> None:
    """Drop clue 9 (milk in the middle house) and the puzzle becomes ambiguous."""
    theme = load_theme("classic_houses")
    clues = [
        c
        for c in _einstein_clues()
        if not (isinstance(c, AbsolutePosition) and c.category == "drink" and c.value == "milk")
    ]
    assert count_solutions(_einstein_puzzle(clues), theme, limit=2) >= 2
    assert is_uniquely_solvable(_einstein_puzzle(clues), theme) is False


def test_empty_puzzle_has_many_solutions() -> None:
    """Sanity: with no clues, a 5x5 puzzle is wide-open."""
    theme = load_theme("classic_houses")
    assert count_solutions(_einstein_puzzle(clues=[]), theme, limit=2) == 2
    assert is_uniquely_solvable(_einstein_puzzle(clues=[]), theme) is False


def test_einstein_with_immediate_left_of_collapses_two_clues_to_one() -> None:
    """One ImmediateLeftOf replaces the Adjacency+RelativePosition pair for clue 6."""
    theme = load_theme("classic_houses")
    clues = [
        c
        for c in _einstein_clues()
        if not (
            (isinstance(c, Adjacency) and {c.value_a, c.value_b} == {"ivory", "green"})
            or (isinstance(c, RelativePosition) and c.value_a == "ivory" and c.value_b == "green")
        )
    ]
    clues.append(
        ImmediateLeftOf(category_a="color", value_a="ivory", category_b="color", value_b="green")
    )
    sol = solve(_einstein_puzzle(clues), theme)
    assert sol is not None
    assert sol.assignments == _EXPECTED_SOLUTION
    assert is_uniquely_solvable(_einstein_puzzle(clues), theme) is True


def test_immediate_left_of_rejects_swapped_direction() -> None:
    """ImmediateLeftOf is directional: pinning b to the rightmost slot leaves
    no room for a one further right, so the puzzle is unsatisfiable."""
    theme = load_theme("classic_houses")
    clues: list[Clue] = [
        ImmediateLeftOf(category_a="color", value_a="ivory", category_b="color", value_b="green"),
        AbsolutePosition(category="color", value="ivory", position=4),
    ]
    assert solve(_einstein_puzzle(clues), theme) is None
