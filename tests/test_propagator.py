"""Tests for the wave-loop deduction tracer.

The tracer is the second solver: it mirrors a human solving by pure
deduction, counting how many propagation waves a puzzle needs. The classic
zebra riddle is the headline case — it is famously solvable with no guessing,
so the tracer must fully resolve it and agree with the OR-Tools solution.
"""

from __future__ import annotations

import random

from hypothesis import given, settings
from hypothesis import strategies as st

from csp_generator.generator.pipeline import generate
from csp_generator.models import AbsolutePosition, Clue, Puzzle
from csp_generator.solver.propagator import trace
from csp_generator.themes.loader import load_theme

from .test_solver import _einstein_puzzle


def test_einstein_riddle_solved_by_pure_deduction() -> None:
    theme = load_theme("classic_houses")
    result = trace(_einstein_puzzle(), theme)

    assert result.solved is True
    assert result.requires_guess is False
    assert result.deduction_depth >= 1
    # The zebra riddle is not arc-consistent solvable: it provably needs at
    # least one level of contradiction-driven case analysis.
    assert result.hypothesis_depth >= 1
    # The famous answer (pet=zebra) is reached, not given — it resolves on
    # some wave after the first.
    assert result.question_target_wave is not None
    assert result.question_target_wave >= 1


def test_empty_puzzle_requires_guessing() -> None:
    theme = load_theme("classic_houses")
    result = trace(_einstein_puzzle(clues=[]), theme)

    assert result.solved is False
    assert result.requires_guess is True


def test_question_target_wave_tracks_when_the_answer_resolves() -> None:
    theme = load_theme("classic_houses")
    # A single clue that pins the answer directly: zebra resolves on wave 1,
    # but the rest of the grid stays open so the puzzle is not solved.
    clue: Clue = AbsolutePosition(category="pet", value="zebra", position=0)
    puzzle = Puzzle(id="t", theme_id="classic_houses", size=5, clues=[clue])
    result = trace(puzzle, theme)

    assert result.question_target_wave == 1
    assert result.solved is False


def test_branching_factor_is_a_sane_average() -> None:
    theme = load_theme("classic_houses")
    empty = trace(_einstein_puzzle(clues=[]), theme)
    # Nothing deduced: every cell still has all `size` positions open, so the
    # average branching is exactly the grid size.
    assert empty.branching_factor == float(theme.size)

    solved = trace(_einstein_puzzle(), theme)
    # As the grid resolves the average candidate count falls below the
    # starting size but never drops under 1.
    assert 1.0 <= solved.branching_factor < float(theme.size)


@given(seed=st.integers(min_value=0, max_value=49))
@settings(max_examples=5, deadline=None)
def test_generated_puzzles_resolve_by_pure_deduction(seed: int) -> None:
    theme = load_theme("classic_houses")
    puzzle = generate(theme, rng=random.Random(seed), n_restarts=1)
    result = trace(puzzle, theme)

    assert result.solved is True
    assert result.requires_guess is False
    assert result.hypothesis_depth >= 0
    assert puzzle.solution is not None
    # The deduced grid must match the solution OR-Tools verified as unique.
    for category, values in theme.attributes.items():
        for value in values:
            assert result.state.resolved_position(category, value) == (
                puzzle.solution.position_of(category, value)
            )
