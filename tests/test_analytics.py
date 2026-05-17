"""Tests for the analytics layer: clue variety and composite difficulty."""

from __future__ import annotations

import math

from csp_generator.analytics.difficulty import composite_difficulty
from csp_generator.analytics.variety import clue_variety
from csp_generator.models import (
    AbsolutePosition,
    Adjacency,
    Clue,
    PositiveAssociation,
)


def _difficulty(
    *,
    deduction_depth: int = 8,
    hypothesis_depth: int = 0,
    branching_factor: float = 2.0,
    clue_count: int = 15,
    clue_variety: float = 0.5,
    size: int = 5,
) -> float:
    return composite_difficulty(
        deduction_depth=deduction_depth,
        hypothesis_depth=hypothesis_depth,
        branching_factor=branching_factor,
        clue_count=clue_count,
        clue_variety=clue_variety,
        size=size,
    )


def _pa(i: int) -> PositiveAssociation:
    return PositiveAssociation(
        category_a="color", value_a=f"c{i}", category_b="pet", value_b=f"p{i}"
    )


def _abs(i: int) -> AbsolutePosition:
    return AbsolutePosition(category="color", value=f"c{i}", position=i)


def _adj(i: int) -> Adjacency:
    return Adjacency(category_a="color", value_a=f"c{i}", category_b="pet", value_b=f"p{i}")


# ---------------------------------------------------------------------------
# clue_variety — Pielou evenness of the clue-type distribution, 0..1
# ---------------------------------------------------------------------------


def test_variety_is_zero_for_empty_or_single_type() -> None:
    assert clue_variety([]) == 0.0
    assert clue_variety([_pa(0), _pa(1), _pa(2)]) == 0.0


def test_variety_is_one_for_an_even_two_type_mix() -> None:
    clues: list[Clue] = [_pa(0), _pa(1), _abs(0), _abs(1)]
    assert clue_variety(clues) == 1.0


def test_variety_is_one_for_an_even_three_type_mix() -> None:
    clues: list[Clue] = [_pa(0), _abs(0), _adj(0)]
    assert clue_variety(clues) == 1.0


def test_variety_drops_when_the_mix_is_skewed() -> None:
    even: list[Clue] = [_pa(0), _pa(1), _abs(0), _abs(1)]
    skewed: list[Clue] = [_pa(0), _pa(1), _pa(2), _abs(0)]
    assert clue_variety(skewed) < clue_variety(even)
    # 3:1 split of two types has a known normalised entropy.
    expected = (-(0.75 * math.log2(0.75)) - (0.25 * math.log2(0.25))) / math.log2(2)
    assert clue_variety(skewed) == expected


# ---------------------------------------------------------------------------
# composite_difficulty — 0..10 scalar
# ---------------------------------------------------------------------------


def test_difficulty_stays_in_range_even_at_extremes() -> None:
    floor = _difficulty(
        deduction_depth=0,
        hypothesis_depth=0,
        branching_factor=1.0,
        clue_count=999,
        clue_variety=0.0,
    )
    ceiling = _difficulty(
        deduction_depth=10_000,
        hypothesis_depth=99,
        branching_factor=99.0,
        clue_count=0,
        clue_variety=1.0,
    )
    assert 0.0 <= floor <= 10.0
    assert 0.0 <= ceiling <= 10.0
    assert floor < ceiling


def test_difficulty_rises_with_deduction_depth() -> None:
    assert _difficulty(deduction_depth=4) < _difficulty(deduction_depth=18)


def test_case_analysis_makes_a_puzzle_harder() -> None:
    assert _difficulty(hypothesis_depth=0) < _difficulty(hypothesis_depth=1)
    assert _difficulty(hypothesis_depth=1) < _difficulty(hypothesis_depth=2)


def test_more_branching_and_fewer_clues_are_harder() -> None:
    assert _difficulty(branching_factor=1.5) < _difficulty(branching_factor=4.0)
    assert _difficulty(clue_count=22) < _difficulty(clue_count=11)


def test_easy_and_hard_configs_land_in_sensible_bands() -> None:
    easy = _difficulty(
        deduction_depth=3,
        hypothesis_depth=0,
        branching_factor=1.3,
        clue_count=22,
        clue_variety=0.2,
    )
    hard = _difficulty(
        deduction_depth=22,
        hypothesis_depth=2,
        branching_factor=3.8,
        clue_count=12,
        clue_variety=0.8,
    )
    assert easy < 4.0
    assert hard > 7.0
