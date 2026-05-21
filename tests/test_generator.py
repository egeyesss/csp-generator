"""Tests for the puzzle-generation pipeline.

Covers solution generation, minimum-clue selection, and the end-to-end
generate() call. Integration with OR-Tools (via is_uniquely_solvable) is
deliberate — we want to catch real solver regressions, not hide behind mocks.
"""

from __future__ import annotations

import random

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from csp_generator.clues.enumerator import enumerate_valid_clues, is_satisfied_by
from csp_generator.generator.pipeline import generate
from csp_generator.generator.selection import select_minimum_clues
from csp_generator.generator.solution import generate_solution
from csp_generator.models import PositiveAssociation, Puzzle, Theme
from csp_generator.solver.ortools_solver import is_uniquely_solvable
from csp_generator.themes.loader import load_theme


@pytest.fixture(scope="module")
def classic() -> Theme:
    return load_theme("classic_houses")


# ---------------------------------------------------------------------------
# generate_solution
# ---------------------------------------------------------------------------


def test_solution_contains_all_values(classic: Theme) -> None:
    sol = generate_solution(classic, random.Random(0))
    for category, expected in classic.attributes.items():
        assert sorted(sol.assignments[category]) == sorted(expected)


def test_solution_theme_id_matches(classic: Theme) -> None:
    sol = generate_solution(classic)
    assert sol.theme_id == classic.id


def test_solution_reproducible_with_seed(classic: Theme) -> None:
    a = generate_solution(classic, random.Random(42))
    b = generate_solution(classic, random.Random(42))
    assert a == b


def test_different_seeds_give_different_solutions(classic: Theme) -> None:
    # 5x5 grid has 5!^5 ≈ 25B permutations; collision probability is negligible
    results = {
        frozenset(
            (k, tuple(v))
            for k, v in generate_solution(classic, random.Random(i)).assignments.items()
        )
        for i in range(10)
    }
    assert len(results) > 1


# ---------------------------------------------------------------------------
# select_minimum_clues
# ---------------------------------------------------------------------------


def test_selection_result_is_uniquely_solvable(classic: Theme) -> None:
    rng = random.Random(7)
    solution = generate_solution(classic, rng)
    pool = enumerate_valid_clues(solution, classic)
    clues = select_minimum_clues(pool, solution, classic, random.Random(7), n_restarts=1)
    puzzle = Puzzle(id="test", theme_id=classic.id, size=classic.size, clues=clues)
    assert is_uniquely_solvable(puzzle, classic)


def test_selection_result_is_subset_of_pool(classic: Theme) -> None:
    rng = random.Random(99)
    solution = generate_solution(classic, rng)
    pool = enumerate_valid_clues(solution, classic)
    clues = select_minimum_clues(pool, solution, classic, random.Random(99), n_restarts=1)
    pool_set = set(pool)
    assert all(c in pool_set for c in clues)


def test_selection_reduces_clue_count(classic: Theme) -> None:
    rng = random.Random(3)
    solution = generate_solution(classic, rng)
    pool = enumerate_valid_clues(solution, classic)
    clues = select_minimum_clues(pool, solution, classic, random.Random(3), n_restarts=1)
    assert len(clues) < len(pool)


def test_multi_restart_no_larger_than_single(classic: Theme) -> None:
    solution = generate_solution(classic, random.Random(13))
    pool = enumerate_valid_clues(solution, classic)
    single = select_minimum_clues(pool, solution, classic, random.Random(13), n_restarts=1)
    multi = select_minimum_clues(pool, solution, classic, random.Random(13), n_restarts=3)
    assert len(multi) <= len(single)


# ---------------------------------------------------------------------------
# generate (end-to-end)
# ---------------------------------------------------------------------------


def test_generated_puzzle_is_uniquely_solvable(classic: Theme) -> None:
    puzzle = generate(classic, rng=random.Random(0), n_restarts=1)
    assert is_uniquely_solvable(puzzle, classic)


def test_generated_puzzle_has_metrics(classic: Theme) -> None:
    puzzle = generate(classic, rng=random.Random(1), n_restarts=1)
    assert puzzle.metrics is not None
    assert puzzle.metrics.clue_count == len(puzzle.clues)


def test_generated_puzzle_has_analytics_filled_in(classic: Theme) -> None:
    puzzle = generate(classic, rng=random.Random(1), n_restarts=1)
    m = puzzle.metrics
    assert m is not None
    # The tracer + analytics layer must populate every metric, not leave the
    # placeholders at None.
    assert m.deduction_depth is not None and m.deduction_depth >= 1
    assert m.hypothesis_depth is not None and m.hypothesis_depth >= 0
    assert m.branching_factor is not None and m.branching_factor >= 1.0
    assert m.clue_variety is not None and 0.0 <= m.clue_variety <= 1.0
    assert m.composite_difficulty is not None
    assert 0.0 <= m.composite_difficulty <= 10.0


def test_generated_puzzle_has_solution(classic: Theme) -> None:
    puzzle = generate(classic, rng=random.Random(2), n_restarts=1)
    assert puzzle.solution is not None


def test_generated_puzzle_clues_satisfied_by_solution(classic: Theme) -> None:
    puzzle = generate(classic, rng=random.Random(3), n_restarts=1)
    assert puzzle.solution is not None
    for clue in puzzle.clues:
        assert is_satisfied_by(clue, puzzle.solution)


def test_generated_puzzle_has_unique_id(classic: Theme) -> None:
    a = generate(classic, rng=random.Random(10), n_restarts=1)
    b = generate(classic, rng=random.Random(11), n_restarts=1)
    assert a.id != b.id


def test_clue_count_5x5_in_expected_range(classic: Theme) -> None:
    """Near-minimal clue sets for 5x5 should land in the 14-18 range.

    The Einstein riddle (the canonical 5x5 reference) has 15 clues. A greedy
    approximation won't always hit the true minimum, so we allow a small buffer.
    """
    counts = [len(generate(classic, rng=random.Random(i), n_restarts=5).clues) for i in range(5)]
    avg = sum(counts) / len(counts)
    assert 14 <= avg <= 19, f"average {avg:.1f} out of expected range; per-seed: {counts}"


def test_question_target_not_in_clues_as_pa(classic: Theme) -> None:
    """No PA clue should directly state the answer (pet=zebra on either side)."""
    puzzle = generate(classic, rng=random.Random(0), n_restarts=3)
    qt = classic.question_target
    assert qt is not None
    cat, val = qt
    for clue in puzzle.clues:
        if isinstance(clue, PositiveAssociation):
            assert not (
                clue.category_a == cat and clue.value_a == val
            ), f"PA directly states question target on side A: {clue}"
            assert not (
                clue.category_b == cat and clue.value_b == val
            ), f"PA directly states question target on side B: {clue}"


def test_puzzle_stores_question(classic: Theme) -> None:
    puzzle = generate(classic, rng=random.Random(1), n_restarts=1)
    assert puzzle.question == classic.question_target


def test_generate_without_question_target() -> None:
    from csp_generator.models import Theme

    theme = Theme(
        id="tiny",
        name="Tiny",
        entity_label="slot",
        attributes={"color": ["red", "blue", "green"], "shape": ["circle", "square", "triangle"]},
    )
    puzzle = generate(theme, rng=random.Random(0), n_restarts=1)
    assert puzzle.question is None
    assert is_uniquely_solvable(puzzle, theme)


@given(seed=st.integers(min_value=0, max_value=49))
@settings(max_examples=5, deadline=120_000)
def test_generate_always_uniquely_solvable(seed: int) -> None:
    theme = load_theme("classic_houses")
    puzzle = generate(theme, rng=random.Random(seed), n_restarts=1)
    assert is_uniquely_solvable(puzzle, theme)


# ---------------------------------------------------------------------------
# Difficulty floor (opt-in)
# ---------------------------------------------------------------------------


def test_generate_respects_difficulty_floor(classic: Theme) -> None:
    """A reachable floor should be honored — every returned puzzle clears it."""
    puzzle = generate(
        classic, rng=random.Random(0), n_restarts=1, min_difficulty=3.0, max_retries=5
    )
    assert puzzle.metrics is not None
    assert puzzle.metrics.composite_difficulty is not None
    assert puzzle.metrics.composite_difficulty >= 3.0


def test_generate_returns_best_effort_when_floor_unreachable(classic: Theme) -> None:
    """When the floor can't be cleared in max_retries, return the best attempt."""
    # 9.5 is well above what 5x5 puzzles land at on this theme; the loop will
    # exhaust max_retries and return the highest-difficulty attempt without
    # crashing.
    puzzle = generate(
        classic, rng=random.Random(0), n_restarts=1, min_difficulty=9.5, max_retries=2
    )
    assert puzzle.metrics is not None
    assert puzzle.metrics.composite_difficulty is not None
    assert puzzle.solution is not None


def test_generate_default_has_no_floor(classic: Theme) -> None:
    """Programmatic callers shouldn't see new behavior unless they opt in."""
    # With min_difficulty=None (the default), the loop runs once — no retries
    # even if the puzzle's difficulty is low.
    puzzle = generate(classic, rng=random.Random(0), n_restarts=1)
    assert puzzle.metrics is not None


def test_generate_rejects_nonpositive_max_retries(classic: Theme) -> None:
    """max_retries < 1 with a floor set should raise cleanly, not assert."""
    with pytest.raises(ValueError, match="max_retries"):
        generate(classic, rng=random.Random(0), n_restarts=1, min_difficulty=5.0, max_retries=0)


def test_generate_4x4_applies_default_difficulty_floor() -> None:
    """4x4 themes should default to min_difficulty=3.5 so generated puzzles
    don't fall into the trivial cluster (d < 3.0, hypothesis_depth == 0).

    Based on the batch analysis on `restaurant`, ~38% of unfiltered runs land
    in [3.5, 4.5] and ~48% land in [3.5, 5.0]. With max_retries=10 (the CLI
    default), clearing 3.5 is near-certain in practice.
    """
    restaurant = load_theme("restaurant")
    assert restaurant.size == 4

    # Seed 3 was verified to produce d=2.36 on a single attempt (no retry),
    # well below the 3.5 floor. If the default is wired in correctly, the
    # retry loop will resample until a higher-difficulty puzzle is found.
    puzzle = generate(restaurant, rng=random.Random(3), n_restarts=1)
    assert puzzle.metrics is not None
    assert puzzle.metrics.composite_difficulty is not None
    assert puzzle.metrics.composite_difficulty >= 3.5


def test_generate_default_no_floor_on_5x5(classic: Theme) -> None:
    """5x5 themes should not pick up the 4x4 floor — programmatic callers
    still get a single attempt with no difficulty gating unless they opt in.
    """
    assert classic.size == 5
    puzzle = generate(classic, rng=random.Random(0), n_restarts=1)
    assert puzzle.metrics is not None
    assert puzzle.metrics.composite_difficulty is not None


def test_generate_cli_rejects_zero_max_retries() -> None:
    """The CLI flag should validate upfront so users see a clean error."""
    from click.testing import CliRunner

    from csp_generator.cli import main

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["generate", "--theme", "classic_houses", "--max-retries", "0"],
    )
    assert result.exit_code != 0
    assert "max-retries" in result.output.lower() or "max_retries" in result.output.lower()


# ---------------------------------------------------------------------------
# Multi-theme smoke: every shipped theme can produce a valid puzzle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("theme_id", ["office", "dorm", "restaurant"])
def test_generate_for_new_theme(theme_id: str) -> None:
    from csp_generator.clues.templates import render

    theme = load_theme(theme_id)
    puzzle = generate(theme, rng=random.Random(0), n_restarts=1)
    assert is_uniquely_solvable(puzzle, theme)
    assert puzzle.question == theme.question_target
    # Every clue should render to a non-empty sentence under the theme's descriptors.
    for clue in puzzle.clues:
        text = render(clue, theme)
        assert text and text.endswith(".")
