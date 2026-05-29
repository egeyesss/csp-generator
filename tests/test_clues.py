"""Tests for the clue type system.

This file covers the two newer clue types (Disjunction, Conditional) and the
clue layer above them: natural-language rendering and enumerate_valid_clues.
Constraint translation for the original five clue types is covered indirectly
in test_solver.py via the Einstein riddle.
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from csp_generator.clues.enumerator import enumerate_valid_clues, is_satisfied_by
from csp_generator.clues.templates import render
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
)
from csp_generator.solver import count_solutions, solve
from csp_generator.themes import load_theme

# ---------------------------------------------------------------------------
# Model: Disjunction
# ---------------------------------------------------------------------------


def test_disjunction_constructs_with_two_options() -> None:
    clue = Disjunction(
        category_a="pet",
        value_a="dog",
        options=[
            ("nationality", "Spaniard"),
            ("nationality", "Norwegian"),
        ],
    )
    assert clue.type == "disjunction"
    assert len(clue.options) == 2


def test_disjunction_rejects_fewer_than_two_options() -> None:
    with pytest.raises(ValidationError):
        Disjunction(
            category_a="pet",
            value_a="dog",
            options=[("nationality", "Spaniard")],
        )


def test_disjunction_rejects_duplicate_options() -> None:
    with pytest.raises(ValidationError):
        Disjunction(
            category_a="pet",
            value_a="dog",
            options=[
                ("nationality", "Spaniard"),
                ("nationality", "Spaniard"),
            ],
        )


# ---------------------------------------------------------------------------
# Model: Conditional
# ---------------------------------------------------------------------------


def test_conditional_constructs() -> None:
    clue = Conditional(
        if_category_a="nationality",
        if_value_a="Englishman",
        if_category_b="color",
        if_value_b="red",
        then_category_a="drink",
        then_value_a="tea",
        then_category_b="cigarette",
        then_value_b="Old Gold",
    )
    assert clue.type == "conditional"


# ---------------------------------------------------------------------------
# OR-Tools translation
# ---------------------------------------------------------------------------


def _puzzle(clues: Sequence[Clue]) -> Puzzle:
    return Puzzle(id="t", theme_id="classic_houses", size=5, clues=list(clues))


def test_disjunction_satisfiable_when_an_option_holds() -> None:
    """A Disjunction admits at least one solution that matches one of its options."""
    theme = load_theme("classic_houses")
    clue = Disjunction(
        category_a="pet",
        value_a="dog",
        options=[("nationality", "Spaniard"), ("nationality", "Norwegian")],
    )
    sol = solve(_puzzle([clue]), theme)
    assert sol is not None
    dog_pos = sol.position_of("pet", "dog")
    spaniard_pos = sol.position_of("nationality", "Spaniard")
    norwegian_pos = sol.position_of("nationality", "Norwegian")
    assert dog_pos in (spaniard_pos, norwegian_pos)


def test_disjunction_unsat_when_all_options_negated() -> None:
    """Disjunction with both options independently negated has no solutions."""
    theme = load_theme("classic_houses")
    clues: list[Clue] = [
        Disjunction(
            category_a="pet",
            value_a="dog",
            options=[("nationality", "Spaniard"), ("nationality", "Norwegian")],
        ),
        NegativeAssociation(
            category_a="pet", value_a="dog", category_b="nationality", value_b="Spaniard"
        ),
        NegativeAssociation(
            category_a="pet", value_a="dog", category_b="nationality", value_b="Norwegian"
        ),
    ]
    assert solve(_puzzle(clues), theme) is None


def test_conditional_forces_consequent_when_antecedent_holds() -> None:
    """Forcing antecedent true via AbsolutePositions must force the consequent."""
    theme = load_theme("classic_houses")
    clues: list[Clue] = [
        AbsolutePosition(category="nationality", value="Englishman", position=0),
        AbsolutePosition(category="color", value="red", position=0),
        Conditional(
            if_category_a="nationality",
            if_value_a="Englishman",
            if_category_b="color",
            if_value_b="red",
            then_category_a="drink",
            then_value_a="tea",
            then_category_b="nationality",
            then_value_b="Englishman",
        ),
    ]
    sol = solve(_puzzle(clues), theme)
    assert sol is not None
    assert sol.value_at("drink", 0) == "tea"


def test_conditional_vacuous_when_antecedent_false() -> None:
    """If antecedent is forced false, consequent is not constrained."""
    theme = load_theme("classic_houses")
    clues: list[Clue] = [
        AbsolutePosition(category="nationality", value="Englishman", position=0),
        AbsolutePosition(category="color", value="red", position=4),
        Conditional(
            if_category_a="nationality",
            if_value_a="Englishman",
            if_category_b="color",
            if_value_b="red",
            then_category_a="drink",
            then_value_a="tea",
            then_category_b="nationality",
            then_value_b="Englishman",
        ),
    ]
    # The drink at position 0 is free; many solutions exist.
    assert count_solutions(_puzzle(clues), theme, limit=2) == 2


def test_conditional_unsat_when_consequent_violated() -> None:
    """Antecedent forced true and consequent forced false ⇒ no solution."""
    theme = load_theme("classic_houses")
    clues: list[Clue] = [
        AbsolutePosition(category="nationality", value="Englishman", position=0),
        AbsolutePosition(category="color", value="red", position=0),
        AbsolutePosition(category="drink", value="tea", position=4),
        Conditional(
            if_category_a="nationality",
            if_value_a="Englishman",
            if_category_b="color",
            if_value_b="red",
            then_category_a="drink",
            then_value_a="tea",
            then_category_b="nationality",
            then_value_b="Englishman",
        ),
    ]
    assert solve(_puzzle(clues), theme) is None


# ---------------------------------------------------------------------------
# Discriminated-union round-trip
# ---------------------------------------------------------------------------


def test_clue_union_round_trips_new_types() -> None:
    puzzle = Puzzle(
        id="p",
        theme_id="t",
        size=3,
        clues=[
            Disjunction(
                category_a="pet",
                value_a="dog",
                options=[("nationality", "Spaniard"), ("nationality", "Norwegian")],
            ),
            Conditional(
                if_category_a="nationality",
                if_value_a="Englishman",
                if_category_b="color",
                if_value_b="red",
                then_category_a="drink",
                then_value_a="tea",
                then_category_b="cigarette",
                then_value_b="Old Gold",
            ),
            ImmediateLeftOf(
                category_a="color", value_a="ivory", category_b="color", value_b="green"
            ),
        ],
    )
    reloaded = Puzzle.model_validate(puzzle.model_dump())
    assert reloaded == puzzle
    assert isinstance(reloaded.clues[0], Disjunction)
    assert isinstance(reloaded.clues[1], Conditional)
    assert isinstance(reloaded.clues[2], ImmediateLeftOf)


# ---------------------------------------------------------------------------
# Natural-language rendering
# ---------------------------------------------------------------------------


def test_render_positive_association_uses_category_predicate() -> None:
    """PA with a category that has a `predicate` uses it; the other side is subject."""
    theme = load_theme("classic_houses")
    clue = PositiveAssociation(
        category_a="nationality", value_a="Englishman", category_b="color", value_b="red"
    )
    assert render(clue, theme) == "The Englishman lives in the red house."


def test_render_positive_association_is_argument_order_symmetric() -> None:
    """Swapping category_a/category_b in the model produces the same English."""
    theme = load_theme("classic_houses")
    swapped = PositiveAssociation(
        category_a="color", value_a="red", category_b="nationality", value_b="Englishman"
    )
    assert render(swapped, theme) == "The Englishman lives in the red house."


def test_render_positive_association_picks_subject_by_category_order() -> None:
    """When both categories have predicates, the one earlier in theme.categories
    becomes the subject. classic_houses orders categories so the earlier of
    (drink, pet) is `drink`; PA(drink=coffee, pet=dog) → coffee drinker as subject.
    """
    theme = load_theme("classic_houses")
    clue = PositiveAssociation(
        category_a="drink", value_a="coffee", category_b="pet", value_b="dog"
    )
    assert render(clue, theme) == "The coffee drinker owns the dog."


def test_render_positive_association_falls_back_to_copula_without_predicate() -> None:
    """A theme without a predicate for either side falls back to copula `is`."""
    from csp_generator.models import Theme

    theme = Theme(
        id="copula",
        name="Copula",
        entity_label="slot",
        attributes={"x": ["a", "b", "c"], "y": ["1", "2", "3"]},
        descriptors={"x": "the {value} thing", "y": "the {value} number"},
    )
    clue = PositiveAssociation(category_a="x", value_a="a", category_b="y", value_b="1")
    assert render(clue, theme) == "The a thing is the 1 number."


def test_render_negative_association_uses_neutral_phrasing() -> None:
    """NA stays neutral — a copula would read as a category error when one side
    is a location ("The Englishman is not the red house"). NA isn't enumerated
    by the generator today, so the neutral form is the right minimum-cost
    default until a generated puzzle actually needs negated predicates.
    """
    theme = load_theme("classic_houses")
    clue = NegativeAssociation(
        category_a="nationality", value_a="Englishman", category_b="color", value_b="red"
    )
    assert render(clue, theme) == "The Englishman is not paired with the red house."


def test_render_absolute_position_uses_position_label() -> None:
    """`X is at position N` → `X is in <position_label> N`, 1-indexed."""
    theme = load_theme("classic_houses")
    clue = AbsolutePosition(category="nationality", value="Norwegian", position=0)
    assert render(clue, theme) == "The Norwegian is in house 1."


def test_render_adjacency_uses_next_to() -> None:
    theme = load_theme("classic_houses")
    clue = Adjacency(
        category_a="cigarette", value_a="Chesterfields", category_b="pet", value_b="fox"
    )
    assert render(clue, theme) == "The Chesterfields smoker is next to the fox owner."


def test_render_relative_position() -> None:
    theme = load_theme("classic_houses")
    clue = RelativePosition(
        category_a="color", value_a="ivory", category_b="color", value_b="green"
    )
    assert render(clue, theme) == "The ivory house is somewhere to the left of the green house."


def test_render_immediate_left_of() -> None:
    theme = load_theme("classic_houses")
    clue = ImmediateLeftOf(category_a="color", value_a="ivory", category_b="color", value_b="green")
    assert render(clue, theme) == "The ivory house is directly to the left of the green house."


def test_render_disjunction() -> None:
    theme = load_theme("classic_houses")
    clue = Disjunction(
        category_a="pet",
        value_a="dog",
        options=[("nationality", "Spaniard"), ("nationality", "Norwegian")],
    )
    assert render(clue, theme) == (
        "The dog owner shares a house with one of: the Spaniard, the Norwegian."
    )


def test_render_conditional() -> None:
    theme = load_theme("classic_houses")
    clue = Conditional(
        if_category_a="nationality",
        if_value_a="Englishman",
        if_category_b="color",
        if_value_b="red",
        then_category_a="pet",
        then_value_a="dog",
        then_category_b="nationality",
        then_value_b="Spaniard",
    )
    assert render(clue, theme) == (
        "If the Englishman lives in the red house, then the Spaniard owns the dog."
    )


def test_render_falls_back_to_value_when_no_descriptor() -> None:
    """A theme without descriptor templates still produces readable output."""
    from csp_generator.models import Theme

    theme = Theme(
        id="bare",
        name="Bare",
        entity_label="slot",
        attributes={"x": ["a", "b", "c"], "y": ["1", "2", "3"]},
    )
    clue = PositiveAssociation(category_a="x", value_a="a", category_b="y", value_b="1")
    assert render(clue, theme) == "The a (x) is the 1 (y)."


def test_render_office_theme_pa_uses_role_predicate() -> None:
    """Spot-check a non-classic theme also renders naturally."""
    theme = load_theme("office")
    clue = PositiveAssociation(
        category_a="name", value_a="Alice", category_b="role", value_b="engineer"
    )
    assert render(clue, theme) == "Alice is the engineer."


# ---------------------------------------------------------------------------
# is_satisfied_by — semantic clue validation against a solution
# ---------------------------------------------------------------------------


_ZEBRA_SOLUTION = Solution(
    theme_id="classic_houses",
    assignments={
        "color": ["yellow", "blue", "red", "ivory", "green"],
        "nationality": ["Norwegian", "Ukrainian", "Englishman", "Spaniard", "Japanese"],
        "drink": ["water", "tea", "milk", "orange juice", "coffee"],
        "pet": ["fox", "horse", "snails", "dog", "zebra"],
        "cigarette": ["Kools", "Chesterfields", "Old Gold", "Lucky Strike", "Parliaments"],
    },
)


def test_is_satisfied_by_positive_association() -> None:
    assert is_satisfied_by(
        PositiveAssociation(
            category_a="nationality", value_a="Englishman", category_b="color", value_b="red"
        ),
        _ZEBRA_SOLUTION,
    )
    assert not is_satisfied_by(
        PositiveAssociation(
            category_a="nationality", value_a="Englishman", category_b="color", value_b="blue"
        ),
        _ZEBRA_SOLUTION,
    )


def test_is_satisfied_by_negative_association() -> None:
    assert is_satisfied_by(
        NegativeAssociation(
            category_a="nationality", value_a="Englishman", category_b="color", value_b="blue"
        ),
        _ZEBRA_SOLUTION,
    )
    assert not is_satisfied_by(
        NegativeAssociation(
            category_a="nationality", value_a="Englishman", category_b="color", value_b="red"
        ),
        _ZEBRA_SOLUTION,
    )


def test_is_satisfied_by_absolute_position() -> None:
    assert is_satisfied_by(
        AbsolutePosition(category="nationality", value="Norwegian", position=0), _ZEBRA_SOLUTION
    )
    assert not is_satisfied_by(
        AbsolutePosition(category="nationality", value="Norwegian", position=3), _ZEBRA_SOLUTION
    )


def test_is_satisfied_by_adjacency() -> None:
    # Norwegian (pos 0) and blue (pos 1) are adjacent.
    assert is_satisfied_by(
        Adjacency(
            category_a="nationality", value_a="Norwegian", category_b="color", value_b="blue"
        ),
        _ZEBRA_SOLUTION,
    )
    assert not is_satisfied_by(
        Adjacency(
            category_a="nationality", value_a="Norwegian", category_b="color", value_b="green"
        ),
        _ZEBRA_SOLUTION,
    )


def test_is_satisfied_by_relative_position() -> None:
    # Ivory (pos 3) is to the left of green (pos 4).
    assert is_satisfied_by(
        RelativePosition(category_a="color", value_a="ivory", category_b="color", value_b="green"),
        _ZEBRA_SOLUTION,
    )
    assert not is_satisfied_by(
        RelativePosition(category_a="color", value_a="green", category_b="color", value_b="ivory"),
        _ZEBRA_SOLUTION,
    )


def test_is_satisfied_by_immediate_left_of() -> None:
    # Ivory (pos 3) is directly to the left of green (pos 4).
    assert is_satisfied_by(
        ImmediateLeftOf(category_a="color", value_a="ivory", category_b="color", value_b="green"),
        _ZEBRA_SOLUTION,
    )
    # Norwegian (pos 0) is to the left of milk (pos 2), but not directly so.
    assert not is_satisfied_by(
        ImmediateLeftOf(
            category_a="nationality",
            value_a="Norwegian",
            category_b="drink",
            value_b="milk",
        ),
        _ZEBRA_SOLUTION,
    )
    # Direction matters: swapping the two yields a false statement.
    assert not is_satisfied_by(
        ImmediateLeftOf(category_a="color", value_a="green", category_b="color", value_b="ivory"),
        _ZEBRA_SOLUTION,
    )


def test_is_satisfied_by_disjunction() -> None:
    # Dog is at pos 3 (Spaniard); Norwegian is at pos 0. Disjunction holds.
    assert is_satisfied_by(
        Disjunction(
            category_a="pet",
            value_a="dog",
            options=[("nationality", "Spaniard"), ("nationality", "Norwegian")],
        ),
        _ZEBRA_SOLUTION,
    )
    # All options false: dog is not with Ukrainian or Japanese.
    assert not is_satisfied_by(
        Disjunction(
            category_a="pet",
            value_a="dog",
            options=[("nationality", "Ukrainian"), ("nationality", "Japanese")],
        ),
        _ZEBRA_SOLUTION,
    )


def test_is_satisfied_by_conditional() -> None:
    # Antecedent true (Englishman==red), consequent true (snails==Englishman).
    assert is_satisfied_by(
        Conditional(
            if_category_a="nationality",
            if_value_a="Englishman",
            if_category_b="color",
            if_value_b="red",
            then_category_a="pet",
            then_value_a="snails",
            then_category_b="nationality",
            then_value_b="Englishman",
        ),
        _ZEBRA_SOLUTION,
    )
    # Antecedent true, consequent false (dog != Englishman in this solution).
    assert not is_satisfied_by(
        Conditional(
            if_category_a="nationality",
            if_value_a="Englishman",
            if_category_b="color",
            if_value_b="red",
            then_category_a="pet",
            then_value_a="dog",
            then_category_b="nationality",
            then_value_b="Englishman",
        ),
        _ZEBRA_SOLUTION,
    )
    # Antecedent false (Englishman != blue) → vacuously true.
    assert is_satisfied_by(
        Conditional(
            if_category_a="nationality",
            if_value_a="Englishman",
            if_category_b="color",
            if_value_b="blue",
            then_category_a="pet",
            then_value_a="dog",
            then_category_b="nationality",
            then_value_b="Englishman",
        ),
        _ZEBRA_SOLUTION,
    )


# ---------------------------------------------------------------------------
# enumerate_valid_clues — every enumerated clue must be satisfied by the input
# ---------------------------------------------------------------------------


def test_enumerate_valid_clues_are_all_satisfied() -> None:
    theme = load_theme("classic_houses")
    clues = enumerate_valid_clues(_ZEBRA_SOLUTION, theme)
    assert len(clues) > 0
    for clue in clues:
        assert is_satisfied_by(clue, _ZEBRA_SOLUTION), f"clue not satisfied: {clue!r}"


def test_enumerate_valid_clues_has_no_duplicates() -> None:
    theme = load_theme("classic_houses")
    clues = enumerate_valid_clues(_ZEBRA_SOLUTION, theme)
    # Use dump-tuples as a hashable key (Pydantic models with list fields aren't hashable).
    keys = {tuple(sorted(c.model_dump().items())) for c in clues}
    assert len(keys) == len(clues)


def test_enumerate_valid_clues_covers_every_bounded_type() -> None:
    theme = load_theme("classic_houses")
    clues = enumerate_valid_clues(_ZEBRA_SOLUTION, theme)
    types = {c.type for c in clues}
    assert {
        "positive_association",
        "negative_association",
        "absolute_position",
        "adjacency",
        "relative_position",
        "immediate_left_of",
    } <= types


def test_enumerate_includes_ivory_immediately_left_of_green() -> None:
    """The canonical Einstein clue should fall out of the enumerator."""
    theme = load_theme("classic_houses")
    clues = enumerate_valid_clues(_ZEBRA_SOLUTION, theme)
    expected = ImmediateLeftOf(
        category_a="color", value_a="ivory", category_b="color", value_b="green"
    )
    assert expected in clues
    # The swapped direction must not appear — pos_b == pos_a + 1 is directional.
    swapped = ImmediateLeftOf(
        category_a="color", value_a="green", category_b="color", value_b="ivory"
    )
    assert swapped not in clues


def test_enumerate_counts_match_combinatorics() -> None:
    """For a 5x5 solution with 5 categories: 50 PA, 200 NA, 25 AbsPos."""
    theme = load_theme("classic_houses")
    clues = enumerate_valid_clues(_ZEBRA_SOLUTION, theme)
    by_type: dict[str, int] = {}
    for c in clues:
        by_type[c.type] = by_type.get(c.type, 0) + 1
    assert by_type["positive_association"] == 50
    assert by_type["negative_association"] == 200
    assert by_type["absolute_position"] == 25
    # Adjacency and RelativePosition: just assert > 0 — exact counts have tricky
    # canonicalization edge cases for same-category pairs.
    assert by_type["adjacency"] > 0
    assert by_type["relative_position"] > 0


def test_enumerated_clues_keep_einstein_solution() -> None:
    """Sanity: feeding the full enumerated pool to the solver yields the same solution."""
    theme = load_theme("classic_houses")
    clues = enumerate_valid_clues(_ZEBRA_SOLUTION, theme)
    sol = solve(Puzzle(id="t", theme_id="classic_houses", size=5, clues=clues), theme)
    assert sol == _ZEBRA_SOLUTION
