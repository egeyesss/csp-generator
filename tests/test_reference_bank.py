"""Analytics regression against a frozen reference puzzle bank.

`tests/data/reference_puzzles.json` holds nine curated, checked-in puzzles
(three each easy / medium / hard). They were generated once, inspected, and
frozen — so this test pins the *analytics*, not the generator: if a change
to the difficulty model reshuffles the bands, this fails. The difficulty is
recomputed here from the current analytics code, never read from the stored
metrics.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from csp_generator.analytics.difficulty import composite_difficulty
from csp_generator.analytics.variety import clue_variety
from csp_generator.models import Puzzle
from csp_generator.solver.ortools_solver import is_uniquely_solvable
from csp_generator.solver.propagator import trace
from csp_generator.themes.loader import load_theme

_BANK_PATH = Path(__file__).parent / "data" / "reference_puzzles.json"

# Coarse bands. The point of the bank is that any sane difficulty model keeps
# easy clearly below hard; the thresholds have margin so weight tuning within
# reason doesn't trip it, but a band reshuffle does.
_BANDS = {"easy": (0.0, 3.5), "medium": (3.5, 5.5), "hard": (5.5, 10.0)}


Entry = dict[str, Any]


def _bank() -> list[Entry]:
    data: list[Entry] = json.loads(_BANK_PATH.read_text())
    return data


def _difficulty(entry: Entry) -> float:
    theme = load_theme(entry["puzzle"]["theme_id"])
    puzzle = Puzzle(**entry["puzzle"])
    assert is_uniquely_solvable(puzzle, theme), f"{entry['name']} is not unique"
    result = trace(puzzle, theme)
    assert result.requires_guess is False, f"{entry['name']} needs a guess"
    return composite_difficulty(
        deduction_depth=result.deduction_depth,
        hypothesis_depth=result.hypothesis_depth,
        branching_factor=result.branching_factor,
        clue_count=len(puzzle.clues),
        clue_variety=clue_variety(puzzle.clues),
        size=theme.size,
    )


def test_bank_has_three_of_each_band() -> None:
    counts: dict[str, int] = {}
    for entry in _bank():
        counts[entry["band"]] = counts.get(entry["band"], 0) + 1
    assert counts == {"easy": 3, "medium": 3, "hard": 3}


@pytest.mark.parametrize("entry", _bank(), ids=lambda e: e["name"])
def test_each_reference_puzzle_lands_in_its_band(entry: Entry) -> None:
    low, high = _BANDS[entry["band"]]
    score = _difficulty(entry)
    assert low <= score < high, f"{entry['name']} scored {score:.2f}, expected {entry['band']}"


def test_bands_are_strictly_separated() -> None:
    by_band: dict[str, list[float]] = {"easy": [], "medium": [], "hard": []}
    for entry in _bank():
        by_band[entry["band"]].append(_difficulty(entry))
    assert max(by_band["easy"]) < min(by_band["medium"])
    assert max(by_band["medium"]) < min(by_band["hard"])
