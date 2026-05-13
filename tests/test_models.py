"""Basic validation behavior of the Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from csp_generator.models import (
    Adjacency,
    Clue,
    PositiveAssociation,
    Puzzle,
    Solution,
    Theme,
)


def test_theme_size_and_categories() -> None:
    theme = Theme(
        id="t",
        name="T",
        entity_label="thing",
        attributes={"color": ["r", "g", "b"], "shape": ["x", "y", "z"]},
    )
    assert theme.size == 3
    assert theme.categories == ["color", "shape"]


def test_theme_rejects_mismatched_category_sizes() -> None:
    with pytest.raises(ValidationError):
        Theme(
            id="t",
            name="T",
            entity_label="thing",
            attributes={"color": ["r", "g", "b"], "shape": ["x", "y"]},
        )


def test_theme_rejects_duplicate_values() -> None:
    with pytest.raises(ValidationError):
        Theme(
            id="t",
            name="T",
            entity_label="thing",
            attributes={"color": ["r", "r", "b"]},
        )


def test_solution_lookups() -> None:
    sol = Solution(
        theme_id="t",
        assignments={"color": ["red", "green"], "shape": ["circle", "square"]},
    )
    assert sol.value_at("color", 1) == "green"
    assert sol.position_of("shape", "square") == 1


def test_clue_discriminated_union_round_trips() -> None:
    """Puzzle.clues round-trips through dump/validate with the discriminator."""
    puzzle = Puzzle(
        id="p1",
        theme_id="t",
        size=3,
        clues=[
            PositiveAssociation(
                category_a="color", value_a="red", category_b="shape", value_b="circle"
            ),
            Adjacency(category_a="color", value_a="red", category_b="shape", value_b="square"),
        ],
    )
    dumped = puzzle.model_dump()
    reloaded = Puzzle.model_validate(dumped)
    assert reloaded == puzzle
    assert isinstance(reloaded.clues[0], PositiveAssociation)
    assert isinstance(reloaded.clues[1], Adjacency)
    # The Clue alias is for type-checking, sanity-cast to keep mypy/ruff aware.
    _: list[Clue] = list(reloaded.clues)
