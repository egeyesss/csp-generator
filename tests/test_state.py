"""Tests for PossibilityState — the propagation tracer's knowledge model.

PossibilityState tracks, for every (category, value) cell, the set of
positions it could still occupy. These tests pin down the primitive
operations (eliminate / pin / resolved / contradiction) before the per-clue
propagation rules and the wave loop are built on top of it.
"""

from __future__ import annotations

from csp_generator.clues.state import PossibilityState
from csp_generator.models import Theme
from csp_generator.themes.loader import load_theme

# A tiny 3-position theme keeps the candidate sets small enough to assert on
# directly. Two categories is enough to exercise AllDifferent both ways.
SMALL = Theme(
    id="small",
    name="Small",
    entity_label="slot",
    attributes={
        "color": ["red", "green", "blue"],
        "pet": ["dog", "cat", "fish"],
    },
)


def test_fresh_state_has_every_position_possible() -> None:
    state = PossibilityState.from_theme(SMALL)
    assert state.size == 3
    for category, values in SMALL.attributes.items():
        for value in values:
            assert state.possible(category, value) == frozenset({0, 1, 2})


def test_eliminate_removes_position_and_reports_change() -> None:
    state = PossibilityState.from_theme(SMALL)
    assert state.eliminate("color", "red", 1) is True
    assert state.possible("color", "red") == frozenset({0, 2})
    assert state.is_possible("color", "red", 1) is False
    # Eliminating the same position again is a no-op and must report no change
    # so the wave loop can detect a fixpoint.
    assert state.eliminate("color", "red", 1) is False


def test_pin_collapses_cell_to_single_position() -> None:
    state = PossibilityState.from_theme(SMALL)
    assert state.pin("color", "red", 0) is True
    assert state.possible("color", "red") == frozenset({0})
    assert state.resolved_position("color", "red") == 0


def test_pin_enforces_all_different_both_ways() -> None:
    state = PossibilityState.from_theme(SMALL)
    state.pin("color", "red", 0)
    # No other colour can sit at position 0...
    assert state.is_possible("color", "green", 0) is False
    assert state.is_possible("color", "blue", 0) is False
    # ...but a different category is untouched by a colour pin.
    assert state.possible("pet", "dog") == frozenset({0, 1, 2})


def test_pin_is_idempotent() -> None:
    state = PossibilityState.from_theme(SMALL)
    assert state.pin("color", "red", 0) is True
    assert state.pin("color", "red", 0) is False


def test_resolved_position_is_none_until_singleton() -> None:
    state = PossibilityState.from_theme(SMALL)
    assert state.resolved_position("color", "red") is None
    state.eliminate("color", "red", 0)
    assert state.resolved_position("color", "red") is None
    state.eliminate("color", "red", 1)
    assert state.resolved_position("color", "red") == 2


def test_is_resolved_only_when_every_cell_is_a_singleton() -> None:
    state = PossibilityState.from_theme(SMALL)
    assert state.is_resolved() is False
    for category, values in SMALL.attributes.items():
        for position, value in enumerate(values):
            state.pin(category, value, position)
    assert state.is_resolved() is True


def test_contradiction_when_a_cell_loses_every_position() -> None:
    state = PossibilityState.from_theme(SMALL)
    assert state.contradiction() is False
    for position in range(3):
        state.eliminate("pet", "dog", position)
    assert state.contradiction() is True


def test_from_theme_matches_grid_size_of_real_theme() -> None:
    classic = load_theme("classic_houses")
    state = PossibilityState.from_theme(classic)
    assert state.size == 5
    assert state.possible("pet", "zebra") == frozenset({0, 1, 2, 3, 4})
