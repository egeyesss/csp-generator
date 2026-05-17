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
    descriptors: dict[str, str] = Field(default_factory=dict)
    """Per-category noun-phrase template for natural-language rendering.

    Each entry maps a category name to a Python format string containing
    `{value}` — e.g. `"the {value} house"` for the color category. Categories
    without a descriptor fall back to a generic `"the {value} ({category})"`
    phrase.
    """

    question_target: tuple[str, str] | None = None
    """The hidden answer the puzzle solver is supposed to deduce.

    A (category, value) pair — e.g. ("pet", "zebra") for the classic zebra
    puzzle. The generator will not include any PositiveAssociation clue that
    directly states this pair, so the answer must be reached through inference.
    If None, no clues are suppressed.

    Each theme YAML should declare this field. Omitting it means every valid
    clue (including direct giveaways) is available to the selector.
    """

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

        for category, template in self.descriptors.items():
            if category not in self.attributes:
                raise ValueError(f"descriptor declared for unknown category {category!r}")
            if "{value}" not in template:
                raise ValueError(
                    f"descriptor for {category!r} must include the {{value}} placeholder"
                )

        if self.question_target is not None:
            qt_cat, qt_val = self.question_target
            if qt_cat not in self.attributes:
                raise ValueError(f"question_target category {qt_cat!r} not in theme attributes")
            if qt_val not in self.attributes[qt_cat]:
                raise ValueError(f"question_target value {qt_val!r} not in category {qt_cat!r}")

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


class Disjunction(_ClueBase):
    """`(category_a, value_a)` shares a position with one of `options`.

    Each option is a `(category, value)` pair. The clue asserts that the
    `value_a` slot coincides with exactly one of the listed alternatives —
    a generalization of "X is either A or B" to k >= 2 alternatives.
    """

    type: Literal["disjunction"] = "disjunction"
    category_a: str
    value_a: str
    options: list[tuple[str, str]] = Field(min_length=2)

    @model_validator(mode="after")
    def _validate_options(self) -> Disjunction:
        if len(set(self.options)) != len(self.options):
            raise ValueError(f"Disjunction options must be unique, got {self.options}")
        return self


class Conditional(_ClueBase):
    """If `(if_a) == (if_b)` in position, then `(then_a) == (then_b)` in position.

    Both the antecedent and the consequent are positive-association predicates
    over (category, value) pairs.
    """

    type: Literal["conditional"] = "conditional"
    if_category_a: str
    if_value_a: str
    if_category_b: str
    if_value_b: str
    then_category_a: str
    then_value_a: str
    then_category_b: str
    then_value_b: str


Clue = Annotated[
    PositiveAssociation
    | NegativeAssociation
    | AbsolutePosition
    | Adjacency
    | RelativePosition
    | Disjunction
    | Conditional,
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
    hypothesis_depth: int | None = None
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
    question: tuple[str, str] | None = None
    """The hidden answer the solver is asked to deduce, as (category, value).

    Mirrors Theme.question_target. Stored here so the web app and review CLI
    can display the puzzle question without needing to re-load the theme.
    """


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
