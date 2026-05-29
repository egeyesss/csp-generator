"""Tests for the bank stats computation and the `csp-generator stats` CLI.

The stats layer answers: "what does my approved puzzle bank actually look
like?" — distribution of difficulty, clue count, and deduction depth, plus
counts per theme and per grid size. Useful for curating the 30-puzzle launch
bank without re-running the analytics by hand.
"""

from __future__ import annotations

import random
from pathlib import Path

import pytest
from click.testing import CliRunner

from csp_generator.analytics.stats import BankStats, compute_bank_stats
from csp_generator.cli import main as cli_main
from csp_generator.generator.pipeline import generate
from csp_generator.models import Puzzle
from csp_generator.themes.loader import load_theme


def _write(puzzle: Puzzle, directory: Path) -> None:
    (directory / f"{puzzle.id}.json").write_text(puzzle.model_dump_json(indent=2), encoding="utf-8")


@pytest.fixture
def bank_dir(tmp_path: Path) -> Path:
    d = tmp_path / "approved"
    d.mkdir()
    return d


@pytest.fixture
def mixed_bank(bank_dir: Path) -> list[Puzzle]:
    """Two 5x5 classic_houses puzzles and one 4x4 restaurant puzzle."""
    rng = random.Random(0)
    puzzles: list[Puzzle] = []
    classic = load_theme("classic_houses")
    for _ in range(2):
        p = generate(classic, rng=rng, n_restarts=1)
        _write(p, bank_dir)
        puzzles.append(p)
    restaurant = load_theme("restaurant")
    p = generate(restaurant, rng=rng, n_restarts=1)
    _write(p, bank_dir)
    puzzles.append(p)
    return puzzles


def test_compute_bank_stats_counts_per_theme(bank_dir: Path, mixed_bank: list[Puzzle]) -> None:
    stats = compute_bank_stats(bank_dir)
    assert stats.total == 3
    assert stats.per_theme == {"classic_houses": 2, "restaurant": 1}


def test_compute_bank_stats_counts_per_size(bank_dir: Path, mixed_bank: list[Puzzle]) -> None:
    stats = compute_bank_stats(bank_dir)
    assert stats.per_size == {5: 2, 4: 1}


def test_compute_bank_stats_summary_ranges(bank_dir: Path, mixed_bank: list[Puzzle]) -> None:
    """Numeric summaries (min/max/mean) are sensible for each measured field."""
    stats = compute_bank_stats(bank_dir)

    expected_clue_counts = [p.metrics.clue_count for p in mixed_bank if p.metrics is not None]
    assert stats.clue_count.min == min(expected_clue_counts)
    assert stats.clue_count.max == max(expected_clue_counts)
    assert stats.clue_count.mean == pytest.approx(
        sum(expected_clue_counts) / len(expected_clue_counts)
    )


def test_compute_bank_stats_ignores_review_sidecars(
    bank_dir: Path, mixed_bank: list[Puzzle]
) -> None:
    """A *.review.json next to a puzzle must not be counted as a puzzle."""
    (bank_dir / f"{mixed_bank[0].id}.review.json").write_text("{}", encoding="utf-8")
    stats = compute_bank_stats(bank_dir)
    assert stats.total == 3


def test_compute_bank_stats_empty_dir(bank_dir: Path) -> None:
    stats = compute_bank_stats(bank_dir)
    assert stats.total == 0
    assert stats.per_theme == {}
    assert stats.per_size == {}
    assert stats.clue_count.count == 0
    assert stats.clue_count.mean is None
    assert stats.difficulty.mean is None


def test_compute_bank_stats_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        compute_bank_stats(tmp_path / "nope")


def test_bank_stats_is_serializable(bank_dir: Path, mixed_bank: list[Puzzle]) -> None:
    stats = compute_bank_stats(bank_dir)
    round_tripped = BankStats.model_validate_json(stats.model_dump_json())
    assert round_tripped == stats


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_stats_cli_runs_against_real_dir(bank_dir: Path, mixed_bank: list[Puzzle]) -> None:
    runner = CliRunner()
    result = runner.invoke(cli_main, ["stats", "--in", str(bank_dir)])
    assert result.exit_code == 0, result.output
    # Theme + size names + summary header should show up in the table output.
    assert "classic_houses" in result.output
    assert "restaurant" in result.output
    assert "total" in result.output.lower()


def test_stats_cli_empty_dir(bank_dir: Path) -> None:
    """Empty bank still exits 0 and reports a total of 0."""
    runner = CliRunner()
    result = runner.invoke(cli_main, ["stats", "--in", str(bank_dir)])
    assert result.exit_code == 0, result.output
    assert "0" in result.output
