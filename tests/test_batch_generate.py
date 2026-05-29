"""Tests for the batch generation script.

The batch script is a thin wrapper around `csp_generator.generator.pipeline.generate`
that iterates over multiple themes and writes the results into `output/candidates/`
so the review CLI can pick them up. Most of the heavy lifting is already covered
by the pipeline's own tests — this file just nails down the script's filing
behavior and CLI surface.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner
from scripts.batch_generate import main, run_batch

from csp_generator.models import Puzzle


@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "candidates"
    d.mkdir()
    return d


def test_run_batch_writes_one_file_per_puzzle(output_dir: Path) -> None:
    """Per-theme count is honored and each puzzle lands as its own JSON."""
    summary = run_batch(
        themes=["classic_houses"],
        per_theme=2,
        output_dir=output_dir,
        seed=0,
        restarts=1,
    )
    files = list(output_dir.glob("*.json"))
    assert len(files) == 2
    assert summary["classic_houses"] == 2


def test_run_batch_iterates_multiple_themes(output_dir: Path) -> None:
    """Each requested theme contributes its share to the candidate pool."""
    summary = run_batch(
        themes=["classic_houses", "restaurant"],
        per_theme=1,
        output_dir=output_dir,
        seed=0,
        restarts=1,
    )
    assert summary == {"classic_houses": 1, "restaurant": 1}
    files = list(output_dir.glob("*.json"))
    assert len(files) == 2


def test_run_batch_files_are_valid_puzzles(output_dir: Path) -> None:
    """Each written file round-trips through the Puzzle model."""
    run_batch(
        themes=["classic_houses"],
        per_theme=1,
        output_dir=output_dir,
        seed=0,
        restarts=1,
    )
    [path] = list(output_dir.glob("*.json"))
    puzzle = Puzzle.model_validate(json.loads(path.read_text(encoding="utf-8")))
    assert puzzle.theme_id == "classic_houses"
    assert puzzle.solution is not None
    assert puzzle.metrics is not None


def test_run_batch_skips_unknown_theme(output_dir: Path) -> None:
    """An unknown theme id raises rather than silently producing nothing."""
    with pytest.raises(Exception, match="not found"):
        run_batch(
            themes=["does_not_exist"],
            per_theme=1,
            output_dir=output_dir,
            seed=0,
            restarts=1,
        )


def test_cli_runs_end_to_end(output_dir: Path) -> None:
    """Click entry point produces files and exits 0."""
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "--themes",
            "classic_houses",
            "--per-theme",
            "1",
            "--output-dir",
            str(output_dir),
            "--seed",
            "0",
            "--restarts",
            "1",
        ],
    )
    assert result.exit_code == 0, result.output
    assert len(list(output_dir.glob("*.json"))) == 1
