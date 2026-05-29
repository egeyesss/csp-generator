"""Tests for the export builder and the `csp-generator export` CLI command.

The builder is the testable core: it walks an approved-puzzles directory and
produces an ExportBundle. The CLI is a thin Click wrapper that delegates to the
builder and writes the result to disk.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest
from click.testing import CliRunner

from csp_generator.cli import main as cli_main
from csp_generator.export.builder import build_bundle_from_directory
from csp_generator.export.schema import EXPORT_SCHEMA_VERSION, ExportBundle
from csp_generator.generator.pipeline import generate
from csp_generator.models import Puzzle, ReviewData
from csp_generator.themes.loader import load_theme


def _write_pair(puzzle: Puzzle, review: ReviewData | None, approved_dir: Path) -> None:
    """Write a puzzle JSON and (optionally) its review sidecar to disk."""
    (approved_dir / f"{puzzle.id}.json").write_text(
        puzzle.model_dump_json(indent=2), encoding="utf-8"
    )
    if review is not None:
        (approved_dir / f"{puzzle.id}.review.json").write_text(
            review.model_dump_json(indent=2), encoding="utf-8"
        )


@pytest.fixture
def approved_dir(tmp_path: Path) -> Path:
    d = tmp_path / "approved"
    d.mkdir()
    return d


@pytest.fixture
def two_classic_puzzles(approved_dir: Path) -> list[Puzzle]:
    """Two real generated 5x5 classic_houses puzzles, both with review sidecars."""
    theme = load_theme("classic_houses")
    rng = random.Random(42)
    puzzles: list[Puzzle] = []
    for i in range(2):
        p = generate(theme, rng=rng, n_restarts=1)
        review = ReviewData(
            approved=True,
            difficulty_rating=6 + i,
            clue_variety_rating=3,
            aha_factor=4,
            notes=f"puzzle {i}",
        )
        _write_pair(p, review, approved_dir)
        puzzles.append(p)
    return puzzles


def test_builder_skips_review_sidecars(
    approved_dir: Path, two_classic_puzzles: list[Puzzle]
) -> None:
    """Files ending in .review.json must not be treated as puzzles to load."""
    bundle = build_bundle_from_directory(approved_dir)
    assert len(bundle.puzzles) == 2
    ids = {p.id for p in bundle.puzzles}
    assert ids == {p.id for p in two_classic_puzzles}


def test_builder_attaches_review_sidecar(
    approved_dir: Path, two_classic_puzzles: list[Puzzle]
) -> None:
    """Each exported puzzle gets the matching `<id>.review.json` inline."""
    bundle = build_bundle_from_directory(approved_dir)
    for exported in bundle.puzzles:
        assert exported.review is not None
        assert exported.review.approved is True


def test_builder_handles_missing_review(approved_dir: Path) -> None:
    """A puzzle without a sidecar is still exported, with review=None."""
    theme = load_theme("classic_houses")
    rng = random.Random(7)
    puzzle = generate(theme, rng=rng, n_restarts=1)
    _write_pair(puzzle, None, approved_dir)

    bundle = build_bundle_from_directory(approved_dir)
    assert len(bundle.puzzles) == 1
    assert bundle.puzzles[0].review is None


def test_builder_filters_by_theme(approved_dir: Path, two_classic_puzzles: list[Puzzle]) -> None:
    """`theme_filter` keeps only puzzles whose theme_id is in the set."""
    bundle = build_bundle_from_directory(approved_dir, theme_filter={"office"})
    assert bundle.puzzles == []

    bundle = build_bundle_from_directory(approved_dir, theme_filter={"classic_houses"})
    assert len(bundle.puzzles) == 2


def test_builder_filters_by_size(approved_dir: Path, two_classic_puzzles: list[Puzzle]) -> None:
    """`size_filter` keeps only puzzles whose grid size matches."""
    bundle = build_bundle_from_directory(approved_dir, size_filter={4})
    assert bundle.puzzles == []

    bundle = build_bundle_from_directory(approved_dir, size_filter={5})
    assert len(bundle.puzzles) == 2


def test_builder_sorts_puzzles_by_id(approved_dir: Path, two_classic_puzzles: list[Puzzle]) -> None:
    """Output ordering is deterministic — sorted by puzzle id."""
    bundle = build_bundle_from_directory(approved_dir)
    ids = [p.id for p in bundle.puzzles]
    assert ids == sorted(ids)


def test_builder_records_source(approved_dir: Path, two_classic_puzzles: list[Puzzle]) -> None:
    bundle = build_bundle_from_directory(approved_dir, source="output/approved/")
    assert bundle.source == "output/approved/"


def test_builder_empty_dir_yields_empty_bundle(approved_dir: Path) -> None:
    bundle = build_bundle_from_directory(approved_dir)
    assert bundle.puzzles == []
    assert bundle.schema_version == EXPORT_SCHEMA_VERSION


def test_builder_missing_dir_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_bundle_from_directory(tmp_path / "does-not-exist")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_export_cli_writes_versioned_bundle(
    tmp_path: Path,
    approved_dir: Path,
    two_classic_puzzles: list[Puzzle],
) -> None:
    """`csp-generator export` reads --in dir, writes a parseable bundle to --out."""
    out = tmp_path / "exports" / "v1.json"
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["export", "--in", str(approved_dir), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()

    parsed = ExportBundle.model_validate(json.loads(out.read_text(encoding="utf-8")))
    assert parsed.schema_version == EXPORT_SCHEMA_VERSION
    assert len(parsed.puzzles) == 2


def test_export_cli_applies_filters(
    tmp_path: Path,
    approved_dir: Path,
    two_classic_puzzles: list[Puzzle],
) -> None:
    out = tmp_path / "exports" / "v1.json"
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        [
            "export",
            "--in",
            str(approved_dir),
            "--out",
            str(out),
            "--theme",
            "office",
        ],
    )
    assert result.exit_code == 0, result.output
    parsed = ExportBundle.model_validate(json.loads(out.read_text(encoding="utf-8")))
    assert parsed.puzzles == []


def test_export_cli_creates_output_parent(
    tmp_path: Path,
    approved_dir: Path,
    two_classic_puzzles: list[Puzzle],
) -> None:
    """`--out` parent directories are created if missing."""
    out = tmp_path / "deeply" / "nested" / "out.json"
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["export", "--in", str(approved_dir), "--out", str(out)],
    )
    assert result.exit_code == 0, result.output
    assert out.is_file()


def test_export_cli_missing_dir_prints_clean_error(tmp_path: Path) -> None:
    """Bad `--in` path produces a Click usage error, not a raw traceback."""
    out = tmp_path / "out.json"
    runner = CliRunner()
    result = runner.invoke(
        cli_main,
        ["export", "--in", str(tmp_path / "nope"), "--out", str(out)],
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "not found" in result.output.lower() or "error" in result.output.lower()
