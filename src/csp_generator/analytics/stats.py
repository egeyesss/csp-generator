"""Summary statistics over a directory of puzzles.

Answers the curator's question: "what does my approved puzzle bank look like
right now?" — counts per theme, counts per grid size, and min/max/mean for the
three numeric metrics that matter for launch curation (clue count, deduction
depth, composite difficulty).

Pure-function core; the CLI is a thin Rich-rendered wrapper around the same
`BankStats` model.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from csp_generator.models import Puzzle


class Summary(BaseModel):
    """min/max/mean over a numeric field. `count` is how many values were seen."""

    model_config = ConfigDict(frozen=True)

    count: int = Field(ge=0)
    min: float | None = None
    max: float | None = None
    mean: float | None = None


class BankStats(BaseModel):
    """A snapshot of a puzzle directory's overall shape."""

    model_config = ConfigDict(frozen=True)

    total: int = Field(ge=0)
    per_theme: dict[str, int]
    per_size: dict[int, int]
    clue_count: Summary
    deduction_depth: Summary
    difficulty: Summary


def _summarize(values: Iterable[float | int | None]) -> Summary:
    present = [float(v) for v in values if v is not None]
    if not present:
        return Summary(count=0)
    return Summary(
        count=len(present),
        min=min(present),
        max=max(present),
        mean=sum(present) / len(present),
    )


def _load_puzzles(directory: Path) -> list[Puzzle]:
    paths = sorted(p for p in directory.glob("*.json") if not p.name.endswith(".review.json"))
    return [Puzzle.model_validate(json.loads(p.read_text(encoding="utf-8"))) for p in paths]


def compute_bank_stats(directory: Path) -> BankStats:
    """Walk `directory`, load every puzzle JSON, and summarize the bank."""
    if not directory.is_dir():
        raise FileNotFoundError(f"directory not found: {directory}")

    puzzles = _load_puzzles(directory)
    per_theme = dict(Counter(p.theme_id for p in puzzles))
    per_size = dict(Counter(p.size for p in puzzles))

    clue_counts = [p.metrics.clue_count if p.metrics else None for p in puzzles]
    depths = [p.metrics.deduction_depth if p.metrics else None for p in puzzles]
    difficulties = [p.metrics.composite_difficulty if p.metrics else None for p in puzzles]

    return BankStats(
        total=len(puzzles),
        per_theme=per_theme,
        per_size=per_size,
        clue_count=_summarize(clue_counts),
        deduction_depth=_summarize(depths),
        difficulty=_summarize(difficulties),
    )
