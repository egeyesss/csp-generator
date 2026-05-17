"""Per-clue propagation rules for the deduction tracer.

Each rule narrows a :class:`PossibilityState` by removing positions a clue
rules out, the way a human eliminates options while solving. Rules are
*arc-consistency* style: conservative single passes that the wave loop
re-applies until nothing changes. Every rule is **sound** — it only ever
removes a position that is genuinely impossible given the clue, so it can
never eliminate the true solution.

``propagate(clue, state) -> bool`` returns whether the state changed.
"""

from __future__ import annotations

from csp_generator.clues.state import PossibilityState
from csp_generator.models import (
    AbsolutePosition,
    Adjacency,
    Clue,
    Conditional,
    Disjunction,
    NegativeAssociation,
    PositiveAssociation,
    RelativePosition,
)


def _propagate_positive(clue: PositiveAssociation, state: PossibilityState) -> bool:
    """The two cells share a position: each is confined to their overlap."""
    a = (clue.category_a, clue.value_a)
    b = (clue.category_b, clue.value_b)
    shared = state.possible(*a) & state.possible(*b)

    changed = False
    for cell in (a, b):
        for position in state.possible(*cell) - shared:
            changed |= state.eliminate(*cell, position)

    if len(shared) == 1:
        position = next(iter(shared))
        changed |= state.pin(*a, position)
        changed |= state.pin(*b, position)
    return changed


def _propagate_negative(clue: NegativeAssociation, state: PossibilityState) -> bool:
    """The two cells differ: a position only one of them could take is denied
    to the other once that other is the sole occupant of it."""
    a = (clue.category_a, clue.value_a)
    b = (clue.category_b, clue.value_b)

    changed = False
    for this, other in ((a, b), (b, a)):
        other_positions = state.possible(*other)
        if len(other_positions) == 1:
            changed |= state.eliminate(*this, next(iter(other_positions)))
    return changed


def _propagate_absolute(clue: AbsolutePosition, state: PossibilityState) -> bool:
    """The value's position is given outright — pin it."""
    return state.pin(clue.category, clue.value, clue.position)


def _propagate_adjacency(clue: Adjacency, state: PossibilityState) -> bool:
    """Positions differ by 1: a cell may only sit where the partner could be
    immediately on either side of it."""
    a = (clue.category_a, clue.value_a)
    b = (clue.category_b, clue.value_b)

    changed = False
    for this, other in ((a, b), (b, a)):
        other_positions = state.possible(*other)
        for position in state.possible(*this):
            if position - 1 not in other_positions and position + 1 not in other_positions:
                changed |= state.eliminate(*this, position)
    return changed


def _propagate_relative(clue: RelativePosition, state: PossibilityState) -> bool:
    """``value_a`` is strictly left of ``value_b``: ``a`` can't reach as far
    right as ``b``'s last option, and ``b`` can't reach as far left as ``a``'s
    first option."""
    a = (clue.category_a, clue.value_a)
    b = (clue.category_b, clue.value_b)
    a_positions = state.possible(*a)
    b_positions = state.possible(*b)
    if not a_positions or not b_positions:
        return False

    latest_b = max(b_positions)
    earliest_a = min(a_positions)
    changed = False
    for position in a_positions:
        if position >= latest_b:
            changed |= state.eliminate(*a, position)
    for position in b_positions:
        if position <= earliest_a:
            changed |= state.eliminate(*b, position)
    return changed


def _propagate_disjunction(clue: Disjunction, state: PossibilityState) -> bool:
    """``value_a`` coincides with one of the options.

    ``value_a`` is confined to the union of the options' candidate positions.
    If only one option can still meet it, the clue collapses to a plain
    positive association with that option.
    """
    a = (clue.category_a, clue.value_a)
    a_positions = state.possible(*a)

    reachable: set[int] = set()
    viable: list[tuple[str, str]] = []
    for option in clue.options:
        option_positions = state.possible(*option)
        reachable |= set(option_positions)
        if a_positions & option_positions:
            viable.append(option)

    changed = False
    for position in a_positions - reachable:
        changed |= state.eliminate(*a, position)

    if len(viable) == 1:
        (option_category, option_value) = viable[0]
        changed |= _propagate_positive(
            PositiveAssociation(
                category_a=clue.category_a,
                value_a=clue.value_a,
                category_b=option_category,
                value_b=option_value,
            ),
            state,
        )
    return changed


def _must_coincide(
    cell_a: tuple[str, str], cell_b: tuple[str, str], state: PossibilityState
) -> bool:
    """Both cells are resolved to the same single position."""
    pa = state.resolved_position(*cell_a)
    pb = state.resolved_position(*cell_b)
    return pa is not None and pa == pb


def _cannot_coincide(
    cell_a: tuple[str, str], cell_b: tuple[str, str], state: PossibilityState
) -> bool:
    """The two cells have no position in common, so they can never match."""
    return not (state.possible(*cell_a) & state.possible(*cell_b))


def _propagate_conditional(clue: Conditional, state: PossibilityState) -> bool:
    """``if A==B then C==D``.

    Only the two sound, decidable directions are applied: once the antecedent
    is forced true, enforce the consequent; if the consequent is impossible,
    deny the antecedent (contrapositive). An undetermined antecedent yields
    nothing.
    """
    if_a = (clue.if_category_a, clue.if_value_a)
    if_b = (clue.if_category_b, clue.if_value_b)
    then_a = (clue.then_category_a, clue.then_value_a)
    then_b = (clue.then_category_b, clue.then_value_b)

    if _must_coincide(if_a, if_b, state):
        return _propagate_positive(
            PositiveAssociation(
                category_a=then_a[0],
                value_a=then_a[1],
                category_b=then_b[0],
                value_b=then_b[1],
            ),
            state,
        )
    if _cannot_coincide(then_a, then_b, state):
        return _propagate_negative(
            NegativeAssociation(
                category_a=if_a[0], value_a=if_a[1], category_b=if_b[0], value_b=if_b[1]
            ),
            state,
        )
    return False


def propagate(clue: Clue, state: PossibilityState) -> bool:
    """Apply ``clue``'s propagation rule once. Returns True iff state changed."""
    if isinstance(clue, PositiveAssociation):
        return _propagate_positive(clue, state)
    if isinstance(clue, NegativeAssociation):
        return _propagate_negative(clue, state)
    if isinstance(clue, AbsolutePosition):
        return _propagate_absolute(clue, state)
    if isinstance(clue, Adjacency):
        return _propagate_adjacency(clue, state)
    if isinstance(clue, RelativePosition):
        return _propagate_relative(clue, state)
    if isinstance(clue, Disjunction):
        return _propagate_disjunction(clue, state)
    if isinstance(clue, Conditional):
        return _propagate_conditional(clue, state)
    raise NotImplementedError(  # pragma: no cover
        f"no propagation rule for {type(clue).__name__}"
    )


__all__ = ["propagate"]
