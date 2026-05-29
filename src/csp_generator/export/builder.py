"""Build an ExportBundle from a directory of approved puzzles.

The review CLI files an approved puzzle as a pair of sibling JSONs under
`output/approved/`:

  <id>.json         — Puzzle (raw clues + solution + metrics + question)
  <id>.review.json  — ReviewData (the reviewer's verdict)

The builder walks that directory, pairs each puzzle with its sidecar (if any),
loads the puzzle's theme, and wraps the lot in a single versioned bundle ready
to be written to disk and shipped to a downstream consumer.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path

from csp_generator import __version__ as generator_version
from csp_generator.export.schema import (
    EXPORT_SCHEMA_VERSION,
    ExportBundle,
    ExportedPuzzle,
)
from csp_generator.models import Puzzle, ReviewData
from csp_generator.themes.loader import load_theme


def _load_puzzle(path: Path) -> Puzzle:
    return Puzzle.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _load_review(path: Path) -> ReviewData | None:
    if not path.is_file():
        return None
    return ReviewData.model_validate(json.loads(path.read_text(encoding="utf-8")))


def build_bundle_from_directory(
    approved_dir: Path,
    *,
    theme_filter: Iterable[str] | None = None,
    size_filter: Iterable[int] | None = None,
    source: str | None = None,
) -> ExportBundle:
    """Read approved puzzles + reviews from `approved_dir` and bundle them.

    Filters are applied after loading: passing `theme_filter={"office"}` keeps
    only puzzles whose `theme_id` is "office". Output ordering is sorted by
    puzzle id so the bundle is reproducible.
    """
    if not approved_dir.is_dir():
        raise FileNotFoundError(f"approved directory not found: {approved_dir}")

    theme_set = set(theme_filter) if theme_filter is not None else None
    size_set = set(size_filter) if size_filter is not None else None

    puzzle_paths = sorted(
        p for p in approved_dir.glob("*.json") if not p.name.endswith(".review.json")
    )

    exported: list[ExportedPuzzle] = []
    for path in puzzle_paths:
        puzzle = _load_puzzle(path)
        if theme_set is not None and puzzle.theme_id not in theme_set:
            continue
        if size_set is not None and puzzle.size not in size_set:
            continue
        theme = load_theme(puzzle.theme_id)
        review = _load_review(path.with_name(f"{puzzle.id}.review.json"))
        exported.append(ExportedPuzzle.from_puzzle(puzzle, theme, review=review))

    return ExportBundle(
        schema_version=EXPORT_SCHEMA_VERSION,
        generator_version=generator_version,
        source=source,
        puzzles=exported,
    )
