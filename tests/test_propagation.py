"""Tests for per-clue propagation rules.

Each clue type narrows a PossibilityState by removing positions the clue
rules out. The rules must be *sound*: they may only eliminate positions that
are genuinely impossible — never the position the value holds in a true
solution. The final property test pins that invariant down across random
solutions and every enumerated clue.
"""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from csp_generator.clues.enumerator import enumerate_valid_clues
from csp_generator.clues.propagation import propagate
from csp_generator.clues.state import PossibilityState
from csp_generator.generator.solution import generate_solution
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
    Theme,
)
from csp_generator.themes.loader import load_theme

SMALL = Theme(
    id="small",
    name="Small",
    entity_label="slot",
    attributes={
        "color": ["red", "green", "blue"],
        "pet": ["dog", "cat", "fish"],
        "drink": ["tea", "cola", "milk"],
    },
)


def fresh() -> PossibilityState:
    return PossibilityState.from_theme(SMALL)


# ---------------------------------------------------------------------------
# PositiveAssociation: the two cells must share a position
# ---------------------------------------------------------------------------


def test_positive_association_intersects_candidate_sets() -> None:
    state = fresh()
    # red can only be at 0 or 1; dog can only be at 1 or 2 -> both must be at 1.
    state.eliminate("color", "red", 2)
    state.eliminate("pet", "dog", 0)
    clue = PositiveAssociation(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is True
    assert state.resolved_position("color", "red") == 1
    assert state.resolved_position("pet", "dog") == 1


def test_positive_association_pin_triggers_all_different() -> None:
    state = fresh()
    state.eliminate("color", "red", 1)
    state.eliminate("color", "red", 2)  # red pinned to 0
    clue = PositiveAssociation(category_a="color", value_a="red", category_b="pet", value_b="dog")
    propagate(clue, state)
    # dog is forced to 0 with red, so no other pet sits at 0.
    assert state.resolved_position("pet", "dog") == 0
    assert state.is_possible("pet", "cat", 0) is False
    assert state.is_possible("pet", "fish", 0) is False


def test_positive_association_idempotent_when_consistent() -> None:
    state = fresh()
    clue = PositiveAssociation(category_a="color", value_a="red", category_b="pet", value_b="dog")
    propagate(clue, state)  # nothing known yet -> no change
    assert propagate(clue, state) is False


# ---------------------------------------------------------------------------
# NegativeAssociation: the two cells must NOT share a position
# ---------------------------------------------------------------------------


def test_negative_association_removes_position_when_other_side_resolved() -> None:
    state = fresh()
    state.eliminate("pet", "dog", 1)
    state.eliminate("pet", "dog", 2)  # dog pinned to 0
    clue = NegativeAssociation(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is True
    # red cannot also be at 0, but is otherwise unconstrained.
    assert state.is_possible("color", "red", 0) is False
    assert state.possible("color", "red") == frozenset({1, 2})


def test_negative_association_no_change_while_both_sides_open() -> None:
    state = fresh()
    clue = NegativeAssociation(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is False


# ---------------------------------------------------------------------------
# AbsolutePosition: the value sits at a fixed position
# ---------------------------------------------------------------------------


def test_absolute_position_pins_and_clears_siblings() -> None:
    state = fresh()
    clue = AbsolutePosition(category="color", value="green", position=2)
    assert propagate(clue, state) is True
    assert state.resolved_position("color", "green") == 2
    assert state.is_possible("color", "red", 2) is False
    assert state.is_possible("color", "blue", 2) is False


def test_absolute_position_idempotent() -> None:
    state = fresh()
    clue = AbsolutePosition(category="color", value="green", position=2)
    propagate(clue, state)
    assert propagate(clue, state) is False


# ---------------------------------------------------------------------------
# Adjacency: positions differ by exactly 1
# ---------------------------------------------------------------------------


def test_adjacency_confines_partner_to_neighbours() -> None:
    state = fresh()
    state.pin("color", "red", 0)
    clue = Adjacency(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is True
    # Position 0's only neighbour is 1, so dog must be at 1.
    assert state.resolved_position("pet", "dog") == 1


def test_adjacency_no_change_while_both_open() -> None:
    state = fresh()
    clue = Adjacency(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is False


# ---------------------------------------------------------------------------
# RelativePosition: value_a is strictly left of value_b
# ---------------------------------------------------------------------------


def test_relative_position_trims_both_ends() -> None:
    state = fresh()
    clue = RelativePosition(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is True
    # red is left of dog, so red can't be last and dog can't be first.
    assert state.possible("color", "red") == frozenset({0, 1})
    assert state.possible("pet", "dog") == frozenset({1, 2})


def test_relative_position_resolves_partner_when_one_side_pinned() -> None:
    state = fresh()
    state.pin("color", "red", 1)
    clue = RelativePosition(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is True
    assert state.resolved_position("pet", "dog") == 2


# ---------------------------------------------------------------------------
# ImmediateLeftOf: pos_b == pos_a + 1
# ---------------------------------------------------------------------------


def test_immediate_left_of_strips_endpoints() -> None:
    state = fresh()
    clue = ImmediateLeftOf(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is True
    # red can't be at the rightmost slot; dog can't be at the leftmost.
    assert state.possible("color", "red") == frozenset({0, 1})
    assert state.possible("pet", "dog") == frozenset({1, 2})


def test_immediate_left_of_pins_partner_when_one_side_resolved() -> None:
    state = fresh()
    state.pin("color", "red", 1)
    clue = ImmediateLeftOf(category_a="color", value_a="red", category_b="pet", value_b="dog")
    assert propagate(clue, state) is True
    assert state.resolved_position("pet", "dog") == 2


def test_immediate_left_of_no_change_while_both_open_only_at_endpoints() -> None:
    """Once endpoints have been stripped, applying the clue again is a no-op."""
    state = fresh()
    clue = ImmediateLeftOf(category_a="color", value_a="red", category_b="pet", value_b="dog")
    propagate(clue, state)
    assert propagate(clue, state) is False


# ---------------------------------------------------------------------------
# Disjunction: value_a coincides with one of the options
# ---------------------------------------------------------------------------


def test_disjunction_confines_to_union_of_options() -> None:
    state = fresh()
    state.pin("pet", "dog", 0)
    state.pin("pet", "cat", 1)
    clue = Disjunction(
        category_a="color",
        value_a="red",
        options=[("pet", "dog"), ("pet", "cat")],
    )
    assert propagate(clue, state) is True
    # red must coincide with dog (pos 0) or cat (pos 1), never position 2.
    assert state.possible("color", "red") == frozenset({0, 1})


def test_disjunction_reduces_to_positive_when_one_option_viable() -> None:
    state = fresh()
    state.pin("color", "red", 2)
    state.eliminate("pet", "cat", 2)  # only dog can still meet red at pos 2
    clue = Disjunction(
        category_a="color",
        value_a="red",
        options=[("pet", "dog"), ("pet", "cat")],
    )
    assert propagate(clue, state) is True
    assert state.resolved_position("pet", "dog") == 2


# ---------------------------------------------------------------------------
# Conditional: antecedent (PA) implies consequent (PA)
# ---------------------------------------------------------------------------


def _conditional() -> Conditional:
    # if red coincides with tea, then dog coincides with green
    return Conditional(
        if_category_a="color",
        if_value_a="red",
        if_category_b="drink",
        if_value_b="tea",
        then_category_a="pet",
        then_value_a="dog",
        then_category_b="color",
        then_value_b="green",
    )


def test_conditional_enforces_consequent_when_antecedent_forced() -> None:
    state = fresh()
    state.pin("color", "red", 0)
    state.pin("drink", "tea", 0)  # antecedent true: red and tea both at 0
    state.pin("color", "green", 1)
    assert propagate(_conditional(), state) is True
    # consequent dog == green now holds, so dog is forced to green's position.
    assert state.resolved_position("pet", "dog") == 1


def test_conditional_denies_antecedent_when_consequent_impossible() -> None:
    state = fresh()
    state.pin("pet", "dog", 0)
    state.pin("color", "green", 1)  # dog and green can never coincide
    state.pin("drink", "tea", 2)
    assert propagate(_conditional(), state) is True
    # consequent can't hold, so the antecedent must fail: red != tea (pos 2).
    assert state.is_possible("color", "red", 2) is False


def test_conditional_no_change_while_undetermined() -> None:
    state = fresh()
    assert propagate(_conditional(), state) is False


# ---------------------------------------------------------------------------
# Soundness: no rule may ever eliminate the true solution
# ---------------------------------------------------------------------------


def _run_to_fixpoint(clues: list[Clue], state: PossibilityState) -> None:
    """Apply every clue repeatedly until a full pass changes nothing.

    Propagation only ever removes candidates, so the state is monotone and
    this terminates; the cap is a defensive guard against a buggy rule.
    """
    for _ in range(1000):
        if not any(propagate(clue, state) for clue in clues):
            return
    raise AssertionError("propagation did not reach a fixpoint")


@given(seed=st.integers(min_value=0, max_value=49))
@settings(max_examples=8, deadline=None)
def test_no_single_clue_eliminates_the_true_solution(seed: int) -> None:
    theme = load_theme("classic_houses")
    solution = generate_solution(theme, random.Random(seed))
    for clue in enumerate_valid_clues(solution, theme):
        state = PossibilityState.from_theme(theme)
        _run_to_fixpoint([clue], state)
        assert not state.contradiction()
        for category, values in theme.attributes.items():
            for value in values:
                true_position = solution.position_of(category, value)
                assert state.is_possible(category, value, true_position)


@given(seed=st.integers(min_value=0, max_value=49))
@settings(max_examples=8, deadline=None)
def test_full_true_pool_resolves_to_the_solution(seed: int) -> None:
    theme = load_theme("classic_houses")
    solution = generate_solution(theme, random.Random(seed))
    state = PossibilityState.from_theme(theme)
    _run_to_fixpoint(enumerate_valid_clues(solution, theme), state)
    assert state.is_resolved()
    for category, values in theme.attributes.items():
        for value in values:
            assert state.resolved_position(category, value) == solution.position_of(category, value)
