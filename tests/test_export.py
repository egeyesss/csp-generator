"""Tests for the export schema and bundle builder.

The export layer takes approved puzzles (Puzzle JSON + ReviewData sidecar) and
emits a versioned bundle a downstream consumer (e.g. the web app) can load
without needing the generator codebase. The bundle carries the full solution,
each clue's raw structure plus its rendered English text, the theme inline,
generation metrics, and the human review record.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from csp_generator import __version__ as generator_version
from csp_generator.export.schema import (
    EXPORT_SCHEMA_VERSION,
    ExportBundle,
    ExportedClue,
    ExportedPuzzle,
)
from csp_generator.models import (
    Adjacency,
    GenerationMetrics,
    PositiveAssociation,
    Puzzle,
    ReviewData,
    Solution,
)
from csp_generator.themes.loader import load_theme


@pytest.fixture
def classic_puzzle() -> Puzzle:
    """A hand-built tiny puzzle stamped against the classic_houses theme.

    Not actually uniquely-solvable — that's not what these tests exercise.
    We need a Puzzle shape with a solution and a couple of clues so the
    exporter has something concrete to convert.
    """
    theme = load_theme("classic_houses")
    solution = Solution(
        theme_id=theme.id,
        assignments={cat: list(values) for cat, values in theme.attributes.items()},
    )
    clues = [
        PositiveAssociation(
            category_a="color",
            value_a="red",
            category_b="nationality",
            value_b="Englishman",
        ),
        Adjacency(
            category_a="drink",
            value_a="milk",
            category_b="pet",
            value_b="dog",
        ),
    ]
    return Puzzle(
        id="00000000-0000-0000-0000-000000000001",
        theme_id=theme.id,
        size=theme.size,
        clues=clues,
        solution=solution,
        metrics=GenerationMetrics(
            clue_count=2,
            deduction_depth=3,
            hypothesis_depth=0,
            branching_factor=2.5,
            clue_variety=0.6,
            composite_difficulty=4.2,
        ),
        question=theme.question_target,
    )


def test_schema_version_is_semver() -> None:
    """The schema version is the contract with downstream consumers."""
    parts = EXPORT_SCHEMA_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


def test_exported_clue_carries_raw_and_rendered(classic_puzzle: Puzzle) -> None:
    """Each exported clue keeps the structured form *and* the rendered text."""
    theme = load_theme("classic_houses")
    raw = classic_puzzle.clues[0]
    ec = ExportedClue.from_clue(raw, theme)
    assert ec.raw == raw
    assert "Englishman" in ec.text
    assert ec.text.endswith(".")


def test_exported_puzzle_from_puzzle_carries_full_payload(classic_puzzle: Puzzle) -> None:
    """`ExportedPuzzle.from_puzzle` preserves solution, theme, metrics, question, clues."""
    theme = load_theme("classic_houses")
    review = ReviewData(
        approved=True,
        difficulty_rating=7,
        clue_variety_rating=3,
        aha_factor=4,
        notes="great puzzle",
    )
    ep = ExportedPuzzle.from_puzzle(classic_puzzle, theme, review=review)

    assert ep.id == classic_puzzle.id
    assert ep.theme == theme
    assert ep.size == theme.size
    assert ep.question == theme.question_target
    assert ep.solution == classic_puzzle.solution
    assert ep.metrics == classic_puzzle.metrics
    assert ep.review == review
    assert len(ep.clues) == len(classic_puzzle.clues)
    assert ep.clues[0].raw == classic_puzzle.clues[0]


def test_exported_puzzle_requires_solution(classic_puzzle: Puzzle) -> None:
    """A puzzle without a known solution can't be exported — exports ship truth."""
    theme = load_theme("classic_houses")
    no_solution = classic_puzzle.model_copy(update={"solution": None})
    with pytest.raises(ValueError, match="solution"):
        ExportedPuzzle.from_puzzle(no_solution, theme)


def test_exported_puzzle_theme_mismatch_rejected(classic_puzzle: Puzzle) -> None:
    """Exporting with the wrong theme is a programming error, not silent."""
    wrong = load_theme("office")
    with pytest.raises(ValueError, match="theme"):
        ExportedPuzzle.from_puzzle(classic_puzzle, wrong)


def test_export_bundle_round_trip(classic_puzzle: Puzzle, tmp_path: Path) -> None:
    """Bundle serializes to JSON and parses back identically."""
    theme = load_theme("classic_houses")
    ep = ExportedPuzzle.from_puzzle(classic_puzzle, theme)
    bundle = ExportBundle(
        schema_version=EXPORT_SCHEMA_VERSION,
        generator_version=generator_version,
        source="approved/",
        puzzles=[ep],
    )

    path = tmp_path / "bundle.json"
    path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    raw = json.loads(path.read_text(encoding="utf-8"))
    parsed = ExportBundle.model_validate(raw)

    assert parsed == bundle


def test_export_bundle_stamps_generated_at_in_utc() -> None:
    """generated_at defaults to now-UTC if omitted; serializes with timezone info."""
    bundle = ExportBundle(
        schema_version=EXPORT_SCHEMA_VERSION,
        generator_version=generator_version,
        puzzles=[],
    )
    assert bundle.generated_at.tzinfo is not None
    # Round-tripped representation must preserve the timezone marker.
    text = bundle.model_dump_json()
    assert "+00:00" in text or "Z" in text
