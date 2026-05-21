"""Enumerate every clue that's true for a given solution.

The puzzle generator works by starting from a complete, random solution and
filtering down to a minimum sufficient clue set. This module produces the
*pool* the filter operates on: every clue, across every type, whose statement
is true under the supplied solution.

Enumeration is exhaustive for the bounded clue types (PositiveAssociation,
NegativeAssociation, AbsolutePosition, Adjacency, RelativePosition,
ImmediateLeftOf). Disjunction and Conditional admit combinatorial families
without a single "canonical" enumeration; richer enumeration for those will
land alongside the minimum-clue-set selection in Week 3 if useful.
"""

from __future__ import annotations

from itertools import combinations

from csp_generator.models import (
    AbsolutePosition,
    Adjacency,
    Clue,
    Conditional,
    Disjunction,
    ImmediateLeftOf,
    NegativeAssociation,
    PositiveAssociation,
    RelativePosition,
    Solution,
    Theme,
)

# ---------------------------------------------------------------------------
# Semantic validation: does a clue hold under a solution?
# ---------------------------------------------------------------------------


def _pos(solution: Solution, category: str, value: str) -> int:
    return solution.position_of(category, value)


def is_satisfied_by(clue: Clue, solution: Solution) -> bool:
    """True iff `clue`'s statement is true under `solution`."""
    if isinstance(clue, PositiveAssociation):
        return _pos(solution, clue.category_a, clue.value_a) == _pos(
            solution, clue.category_b, clue.value_b
        )
    if isinstance(clue, NegativeAssociation):
        return _pos(solution, clue.category_a, clue.value_a) != _pos(
            solution, clue.category_b, clue.value_b
        )
    if isinstance(clue, AbsolutePosition):
        return _pos(solution, clue.category, clue.value) == clue.position
    if isinstance(clue, Adjacency):
        return (
            abs(
                _pos(solution, clue.category_a, clue.value_a)
                - _pos(solution, clue.category_b, clue.value_b)
            )
            == 1
        )
    if isinstance(clue, RelativePosition):
        return _pos(solution, clue.category_a, clue.value_a) < _pos(
            solution, clue.category_b, clue.value_b
        )
    if isinstance(clue, ImmediateLeftOf):
        return (
            _pos(solution, clue.category_b, clue.value_b)
            == _pos(solution, clue.category_a, clue.value_a) + 1
        )
    if isinstance(clue, Disjunction):
        target = _pos(solution, clue.category_a, clue.value_a)
        return any(target == _pos(solution, c, v) for c, v in clue.options)
    if isinstance(clue, Conditional):
        antecedent = _pos(solution, clue.if_category_a, clue.if_value_a) == _pos(
            solution, clue.if_category_b, clue.if_value_b
        )
        consequent = _pos(solution, clue.then_category_a, clue.then_value_a) == _pos(
            solution, clue.then_category_b, clue.then_value_b
        )
        return (not antecedent) or consequent
    raise NotImplementedError(  # pragma: no cover
        f"no semantics for {type(clue).__name__}"
    )


# ---------------------------------------------------------------------------
# Enumeration
# ---------------------------------------------------------------------------


def _enumerate_positive(solution: Solution, theme: Theme) -> list[Clue]:
    out: list[Clue] = []
    cats = sorted(theme.categories)
    for cat_a, cat_b in combinations(cats, 2):
        for val_a in theme.attributes[cat_a]:
            pos_a = _pos(solution, cat_a, val_a)
            val_b = solution.value_at(cat_b, pos_a)
            out.append(
                PositiveAssociation(
                    category_a=cat_a, value_a=val_a, category_b=cat_b, value_b=val_b
                )
            )
    return out


def _enumerate_negative(solution: Solution, theme: Theme) -> list[Clue]:
    out: list[Clue] = []
    cats = sorted(theme.categories)
    for cat_a, cat_b in combinations(cats, 2):
        for val_a in theme.attributes[cat_a]:
            true_partner = solution.value_at(cat_b, _pos(solution, cat_a, val_a))
            for val_b in theme.attributes[cat_b]:
                if val_b == true_partner:
                    continue
                out.append(
                    NegativeAssociation(
                        category_a=cat_a, value_a=val_a, category_b=cat_b, value_b=val_b
                    )
                )
    return out


def _enumerate_absolute(solution: Solution, theme: Theme) -> list[Clue]:
    out: list[Clue] = []
    for category in sorted(theme.categories):
        for value in theme.attributes[category]:
            out.append(
                AbsolutePosition(
                    category=category, value=value, position=_pos(solution, category, value)
                )
            )
    return out


def _enumerate_adjacency(solution: Solution, theme: Theme) -> list[Clue]:
    """Unordered pairs of distinct cells whose positions differ by 1."""
    out: list[Clue] = []
    cells: list[tuple[str, str]] = [
        (cat, val) for cat in sorted(theme.categories) for val in theme.attributes[cat]
    ]
    for (cat_a, val_a), (cat_b, val_b) in combinations(cells, 2):
        if abs(_pos(solution, cat_a, val_a) - _pos(solution, cat_b, val_b)) == 1:
            out.append(Adjacency(category_a=cat_a, value_a=val_a, category_b=cat_b, value_b=val_b))
    return out


def _enumerate_immediate_left(solution: Solution, theme: Theme) -> list[Clue]:
    """Ordered pairs of distinct cells where pos_b == pos_a + 1."""
    out: list[Clue] = []
    cells: list[tuple[str, str]] = [
        (cat, val) for cat in sorted(theme.categories) for val in theme.attributes[cat]
    ]
    for (cat_a, val_a), (cat_b, val_b) in combinations(cells, 2):
        pa = _pos(solution, cat_a, val_a)
        pb = _pos(solution, cat_b, val_b)
        if pb == pa + 1:
            out.append(
                ImmediateLeftOf(category_a=cat_a, value_a=val_a, category_b=cat_b, value_b=val_b)
            )
        elif pa == pb + 1:
            out.append(
                ImmediateLeftOf(category_a=cat_b, value_a=val_b, category_b=cat_a, value_b=val_a)
            )
    return out


def _enumerate_relative(solution: Solution, theme: Theme) -> list[Clue]:
    """Ordered pairs of distinct cells where pos_a < pos_b.

    Canonical direction: a is always to the left of b. Same-category pairs are
    included (e.g. "the ivory house is somewhere to the left of the green house").
    """
    out: list[Clue] = []
    cells: list[tuple[str, str]] = [
        (cat, val) for cat in sorted(theme.categories) for val in theme.attributes[cat]
    ]
    for (cat_a, val_a), (cat_b, val_b) in combinations(cells, 2):
        pa = _pos(solution, cat_a, val_a)
        pb = _pos(solution, cat_b, val_b)
        if pa == pb:
            continue
        if pa < pb:
            out.append(
                RelativePosition(category_a=cat_a, value_a=val_a, category_b=cat_b, value_b=val_b)
            )
        else:
            out.append(
                RelativePosition(category_a=cat_b, value_a=val_b, category_b=cat_a, value_b=val_a)
            )
    return out


def enumerate_valid_clues(solution: Solution, theme: Theme) -> list[Clue]:
    """Every PA / NA / AbsPos / Adj / RP clue true under `solution`.

    Disjunction and Conditional enumeration is intentionally omitted here —
    those families are combinatorially large and don't have a canonical
    finite set; they'll be folded in alongside the minimum-clue-set selector
    when there's a concrete need.
    """
    if solution.theme_id != theme.id:
        raise ValueError(
            f"solution.theme_id {solution.theme_id!r} does not match theme.id {theme.id!r}"
        )
    return (
        _enumerate_positive(solution, theme)
        + _enumerate_negative(solution, theme)
        + _enumerate_absolute(solution, theme)
        + _enumerate_adjacency(solution, theme)
        + _enumerate_relative(solution, theme)
        + _enumerate_immediate_left(solution, theme)
    )


__all__ = ["enumerate_valid_clues", "is_satisfied_by"]
