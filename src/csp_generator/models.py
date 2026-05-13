"""Core data models for the puzzle generator.

These are the shapes everything else passes around: themes (the scenario
templates), clues (the constraint statements shown to a solver), solutions (the
ground-truth attribute assignments), puzzles (theme + clues + optional solution),
plus the bookkeeping models for analytics and human review.

Clue is a discriminated union; concrete clue types share a `type` literal that
Pydantic uses to route validation and serialization. More clue types will be
added as the clue system grows.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------


class Theme(BaseModel):
    """A scenario template: the entity at each position and its attributes.

    A theme is purely structural — it lists attribute categories (e.g. color,
    nationality, drink) and the value pool for each. The puzzle generator picks
    a random valid assignment of values to positions on top of a theme.

    All attribute categories must have the same number of values; that count is
    the puzzle's grid size.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    entity_label: str = Field(min_length=1)
    position_label: str = "position"
    attributes: dict[str, list[str]]

    @model_validator(mode="after")
    def _validate_attributes(self) -> Theme:
        if not self.attributes:
            raise ValueError("theme must declare at least one attribute category")

        sizes = {cat: len(values) for cat, values in self.attributes.items()}
        unique_sizes = set(sizes.values())
        if len(unique_sizes) != 1:
            raise ValueError(f"attribute categories must all have the same length; got {sizes}")
        size = unique_sizes.pop()
        if size < 2:
            raise ValueError(f"theme size must be >= 2, got {size}")

        for category, values in self.attributes.items():
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate values in category {category!r}: {values}")

        return self

    @property
    def size(self) -> int:
        """Grid size — number of entities/positions in any puzzle for this theme."""
        return len(next(iter(self.attributes.values())))

    @property
    def categories(self) -> list[str]:
        return list(self.attributes.keys())


# ---------------------------------------------------------------------------
# Solution
# ---------------------------------------------------------------------------


class Solution(BaseModel):
    """A complete attribute-to-position assignment for one theme.

    `assignments[category][position]` is the value at that position. Each
    category's value list is a permutation of the theme's value pool.
    """

    model_config = ConfigDict(frozen=True)

    theme_id: str = Field(min_length=1)
    assignments: dict[str, list[str]]

    def value_at(self, category: str, position: int) -> str:
        return self.assignments[category][position]

    def position_of(self, category: str, value: str) -> int:
        return self.assignments[category].index(value)


# ---------------------------------------------------------------------------
# Clue types (discriminated union)
# ---------------------------------------------------------------------------


class _ClueBase(BaseModel):
    model_config = ConfigDict(frozen=True)


class PositiveAssociation(_ClueBase):
    """Two attribute values share a position. E.g. "the Brit lives in the red house"."""

    type: Literal["positive_association"] = "positive_association"
    category_a: str
    value_a: str
    category_b: str
    value_b: str


class NegativeAssociation(_ClueBase):
    """Two attribute values do not share a position."""

    type: Literal["negative_association"] = "negative_association"
    category_a: str
    value_a: str
    category_b: str
    value_b: str


class AbsolutePosition(_ClueBase):
    """An attribute value is at a specific position (0-indexed)."""

    type: Literal["absolute_position"] = "absolute_position"
    category: str
    value: str
    position: int = Field(ge=0)


class Adjacency(_ClueBase):
    """Two attribute values are at adjacent positions (|pos_a - pos_b| == 1)."""

    type: Literal["adjacency"] = "adjacency"
    category_a: str
    value_a: str
    category_b: str
    value_b: str


class RelativePosition(_ClueBase):
    """`value_a` is somewhere to the left of `value_b` (pos_a < pos_b)."""

    type: Literal["relative_position"] = "relative_position"
    category_a: str
    value_a: str
    category_b: str
    value_b: str


Clue = Annotated[
    PositiveAssociation | NegativeAssociation | AbsolutePosition | Adjacency | RelativePosition,
    Field(discriminator="type"),
]


# ---------------------------------------------------------------------------
# Puzzle
# ---------------------------------------------------------------------------


class GenerationMetrics(BaseModel):
    """Numeric properties of a generated puzzle.

    Populated incrementally: clue_count is known right after generation; the
    deduction-depth and difficulty fields are filled in once the custom
    propagator and analytics layer come online.
    """

    model_config = ConfigDict(frozen=True)

    clue_count: int = Field(ge=0)
    deduction_depth: int | None = None
    branching_factor: float | None = None
    clue_variety: float | None = None
    composite_difficulty: float | None = None


class Puzzle(BaseModel):
    """A puzzle: a theme reference, the clue set, and (optionally) the solution.

    The solution is optional so the same model serves both internal generation
    (where the solution is known and carried alongside the clues) and external
    consumers like a future web export (where it would be stripped).
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    theme_id: str = Field(min_length=1)
    size: int = Field(ge=2)
    clues: list[Clue]
    solution: Solution | None = None
    metrics: GenerationMetrics | None = None


# ---------------------------------------------------------------------------
# Review data
# ---------------------------------------------------------------------------


class ReviewData(BaseModel):
    """Structured human-review record captured by the review CLI."""

    approved: bool
    difficulty_rating: int = Field(ge=1, le=10)
    clue_variety_rating: int = Field(ge=1, le=5)
    aha_factor: int = Field(ge=1, le=5)
    notes: str = ""
    rejection_reason: str | None = None
