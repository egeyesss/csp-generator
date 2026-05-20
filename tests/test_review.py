"""Tests for the review session: file shuffling and review-data persistence.

The CLI itself is a thin Click + Rich wrapper around `run_review_session`. The
session takes an injected prompter so we can drive it from tests without
touching stdin.
"""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from pathlib import Path

import pytest

from csp_generator.cli.review import ReviewDecision, run_review_session
from csp_generator.generator.pipeline import generate
from csp_generator.models import Puzzle, ReviewData
from csp_generator.themes.loader import load_theme


def _write_candidate(puzzle: Puzzle, candidates_dir: Path) -> Path:
    path = candidates_dir / f"{puzzle.id}.json"
    path.write_text(puzzle.model_dump_json(indent=2), encoding="utf-8")
    return path


def _puzzle_files(directory: Path) -> list[Path]:
    """*.json files in `directory` excluding review sidecars."""
    return [p for p in directory.glob("*.json") if not p.name.endswith(".review.json")]


@pytest.fixture
def workspace(tmp_path: Path) -> dict[str, Path]:
    """Three empty workflow directories ready for a review session."""
    candidates = tmp_path / "candidates"
    approved = tmp_path / "approved"
    rejected = tmp_path / "rejected"
    for d in (candidates, approved, rejected):
        d.mkdir()
    return {"candidates": candidates, "approved": approved, "rejected": rejected}


@pytest.fixture
def two_candidates(workspace: dict[str, Path]) -> list[Path]:
    """Two real generated puzzles dropped into the candidates dir."""
    theme = load_theme("classic_houses")
    rng = random.Random(0)
    paths = []
    for _ in range(2):
        puzzle = generate(theme, rng=rng, n_restarts=1)
        paths.append(_write_candidate(puzzle, workspace["candidates"]))
    return paths


def _approve_all_prompter() -> Iterator[ReviewDecision]:
    while True:
        yield ReviewDecision(
            review=ReviewData(
                approved=True,
                difficulty_rating=5,
                clue_variety_rating=3,
                aha_factor=3,
                notes="looks fine",
            ),
            skip=False,
        )


def _reject_all_prompter() -> Iterator[ReviewDecision]:
    while True:
        yield ReviewDecision(
            review=ReviewData(
                approved=False,
                difficulty_rating=2,
                clue_variety_rating=2,
                aha_factor=1,
                notes="",
                rejection_reason="too easy",
            ),
            skip=False,
        )


def test_approving_moves_to_approved(
    workspace: dict[str, Path], two_candidates: list[Path]
) -> None:
    results = run_review_session(
        candidates_dir=workspace["candidates"],
        approved_dir=workspace["approved"],
        rejected_dir=workspace["rejected"],
        prompter=_approve_all_prompter(),
    )
    assert results.reviewed == 2
    assert results.approved == 2
    assert results.rejected == 0
    # Candidates dir is now empty; both files live under approved/.
    assert _puzzle_files(workspace["candidates"]) == []
    approved_files = sorted(p.name for p in _puzzle_files(workspace["approved"]))
    expected = sorted(p.name for p in two_candidates)
    assert approved_files == expected


def test_rejecting_moves_to_rejected(
    workspace: dict[str, Path], two_candidates: list[Path]
) -> None:
    results = run_review_session(
        candidates_dir=workspace["candidates"],
        approved_dir=workspace["approved"],
        rejected_dir=workspace["rejected"],
        prompter=_reject_all_prompter(),
    )
    assert results.rejected == 2
    assert _puzzle_files(workspace["candidates"]) == []
    rejected_files = sorted(p.name for p in _puzzle_files(workspace["rejected"]))
    assert rejected_files == sorted(p.name for p in two_candidates)


def test_review_data_sidecar_written(
    workspace: dict[str, Path], two_candidates: list[Path]
) -> None:
    run_review_session(
        candidates_dir=workspace["candidates"],
        approved_dir=workspace["approved"],
        rejected_dir=workspace["rejected"],
        prompter=_approve_all_prompter(),
    )
    for puzzle_path in two_candidates:
        sidecar = workspace["approved"] / f"{puzzle_path.stem}.review.json"
        assert sidecar.is_file(), f"missing review sidecar for {puzzle_path.name}"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        assert data["approved"] is True
        assert data["difficulty_rating"] == 5


def test_skip_leaves_candidate_in_place(
    workspace: dict[str, Path], two_candidates: list[Path]
) -> None:
    skip_then_approve: Iterator[ReviewDecision] = iter(
        [
            ReviewDecision(review=None, skip=True),
            ReviewDecision(
                review=ReviewData(
                    approved=True,
                    difficulty_rating=4,
                    clue_variety_rating=3,
                    aha_factor=3,
                ),
                skip=False,
            ),
        ]
    )
    results = run_review_session(
        candidates_dir=workspace["candidates"],
        approved_dir=workspace["approved"],
        rejected_dir=workspace["rejected"],
        prompter=skip_then_approve,
    )
    assert results.reviewed == 1
    assert results.skipped == 1
    assert len(_puzzle_files(workspace["candidates"])) == 1
    assert len(_puzzle_files(workspace["approved"])) == 1


def test_exhausted_prompter_ends_session_cleanly(
    workspace: dict[str, Path], two_candidates: list[Path]
) -> None:
    """The interactive prompter can break out early (user says \"no\" to continue).

    When it does, the iterator is exhausted before all candidates have been
    seen — the session must exit cleanly with the partial tally, not crash on
    an uncaught StopIteration.
    """
    one_then_done: Iterator[ReviewDecision] = iter(
        [
            ReviewDecision(
                review=ReviewData(
                    approved=True,
                    difficulty_rating=5,
                    clue_variety_rating=3,
                    aha_factor=3,
                ),
                skip=False,
            ),
        ]
    )
    results = run_review_session(
        candidates_dir=workspace["candidates"],
        approved_dir=workspace["approved"],
        rejected_dir=workspace["rejected"],
        prompter=one_then_done,
    )
    assert results.reviewed == 1
    assert results.approved == 1
    # The un-reviewed candidate stays put.
    assert len(_puzzle_files(workspace["candidates"])) == 1


def test_empty_candidates_dir_is_no_op(workspace: dict[str, Path]) -> None:
    results = run_review_session(
        candidates_dir=workspace["candidates"],
        approved_dir=workspace["approved"],
        rejected_dir=workspace["rejected"],
        prompter=_approve_all_prompter(),
    )
    assert results.reviewed == 0
    assert results.approved == 0
    assert results.rejected == 0


def test_cli_review_in_help() -> None:
    from click.testing import CliRunner

    from csp_generator.cli import main

    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "review" in result.output


def test_cli_review_errors_on_missing_dir(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from csp_generator.cli import main

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "review",
            "--candidates-dir",
            str(tmp_path / "does-not-exist"),
            "--approved-dir",
            str(tmp_path / "approved"),
            "--rejected-dir",
            str(tmp_path / "rejected"),
        ],
    )
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_cli_review_no_candidates_exits_cleanly(tmp_path: Path) -> None:
    from click.testing import CliRunner

    from csp_generator.cli import main

    candidates = tmp_path / "candidates"
    candidates.mkdir()
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "review",
            "--candidates-dir",
            str(candidates),
            "--approved-dir",
            str(tmp_path / "approved"),
            "--rejected-dir",
            str(tmp_path / "rejected"),
        ],
    )
    assert result.exit_code == 0
    assert "no candidates" in result.output.lower()


def test_session_skips_review_sidecars(workspace: dict[str, Path]) -> None:
    """Stray *.review.json files in the candidates dir should be left alone."""
    theme = load_theme("classic_houses")
    puzzle = generate(theme, rng=random.Random(0), n_restarts=1)
    _write_candidate(puzzle, workspace["candidates"])
    stray_sidecar = workspace["candidates"] / "leftover.review.json"
    stray_sidecar.write_text("{}", encoding="utf-8")

    results = run_review_session(
        candidates_dir=workspace["candidates"],
        approved_dir=workspace["approved"],
        rejected_dir=workspace["rejected"],
        prompter=_approve_all_prompter(),
    )
    assert results.reviewed == 1
    assert stray_sidecar.is_file()
