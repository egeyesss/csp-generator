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
