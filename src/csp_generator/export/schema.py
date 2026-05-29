"""Pydantic schema for exported puzzle bundles.

The bundle is the contract with downstream consumers (the web app, primarily).
It carries everything a consumer needs to render, grade, and display a puzzle
without depending on the generator codebase: the theme inline, the full solution,
each clue's raw structure plus its rendered English text, the question target,
the generation metrics, and the human review record.

Bumping `EXPORT_SCHEMA_VERSION`:
- Patch (z): clarifications, fixes that don't change parsed shape.
- Minor (y): backward-compatible additions (new optional fields).
- Major (x): breaking changes — renamed or removed fields, type changes.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field

from csp_generator.clues.templates import render
from csp_generator.models import (
    Clue,
    GenerationMetrics,
    Puzzle,
    ReviewData,
    Solution,
    Theme,
)

EXPORT_SCHEMA_VERSION = "1.0.1"


class ExportedClue(BaseModel):
    """One clue in exported form: the structured payload and its rendered text."""

    model_config = ConfigDict(frozen=True)

    raw: Clue
    text: str = Field(min_length=1)

    @classmethod
    def from_clue(cls, clue: Clue, theme: Theme) -> ExportedClue:
        return cls(raw=clue, text=render(clue, theme))


class ExportedPuzzle(BaseModel):
    """A single puzzle, fully self-describing.

    The theme is embedded by value so a consumer doesn't need a theme registry
    or to ship the generator's YAML files. The solution is always present —
    exports are the source of truth for grading.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    theme: Theme
    size: int = Field(ge=2)
    question: tuple[str, str] | None = None
    clues: list[ExportedClue]
    solution: Solution
    metrics: GenerationMetrics | None = None
    review: ReviewData | None = None

    @classmethod
    def from_puzzle(
        cls,
        puzzle: Puzzle,
        theme: Theme,
        *,
        review: ReviewData | None = None,
    ) -> ExportedPuzzle:
        if puzzle.solution is None:
            raise ValueError(f"puzzle {puzzle.id} has no solution; exports require ground truth")
        if puzzle.theme_id != theme.id:
            raise ValueError(
                f"theme mismatch: puzzle.theme_id={puzzle.theme_id!r} " f"but theme.id={theme.id!r}"
            )
        return cls(
            id=puzzle.id,
            theme=theme,
            size=puzzle.size,
            question=puzzle.question,
            clues=[ExportedClue.from_clue(c, theme) for c in puzzle.clues],
            solution=puzzle.solution,
            metrics=puzzle.metrics,
            review=review,
        )


def _now_utc() -> datetime:
    return datetime.now(UTC)


class ExportBundle(BaseModel):
    """A versioned envelope around a list of exported puzzles."""

    model_config = ConfigDict(frozen=True)

    schema_version: str = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    generated_at: datetime = Field(default_factory=_now_utc)
    source: str | None = None
    puzzles: list[ExportedPuzzle]
