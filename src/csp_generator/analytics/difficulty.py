"""Composite difficulty score.

Folds the tracer's reasoning metrics plus the clue mix into a single 0..10
scalar. Each input is mapped onto a saturating ``[0, 1]`` sub-score and the
weighted sum is scaled to 0..10:

- **deduction depth** — how many propagation waves the puzzle takes (primary).
- **hypothesis depth** — nesting of contradiction-driven case analysis; a
  puzzle that needs any is a large step up in difficulty.
- **branching factor** — average candidates per unresolved cell mid-solve.
- **clue sparsity** — fewer clues for the grid size means more inference per
  clue, so a tighter puzzle is harder.
- **clue variety** — a wider type mix is a little more taxing to juggle.

Weights are a first pass; the reference puzzle bank is what calibrates them,
so they're kept here as named constants rather than scattered literals.
"""

from __future__ import annotations

_W_DEPTH = 0.40
_W_HYPOTHESIS = 0.30
_W_BRANCHING = 0.15
_W_SPARSITY = 0.10
_W_VARIETY = 0.05

# Saturation points: inputs at/above these contribute a full sub-score.
_DEPTH_SATURATION = 25.0
_HYPOTHESIS_SATURATION = 2.0


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def composite_difficulty(
    *,
    deduction_depth: int,
    hypothesis_depth: int,
    branching_factor: float,
    clue_count: int,
    clue_variety: float,
    size: int,
) -> float:
    """Difficulty of a puzzle as a 0..10 scalar (higher = harder)."""
    depth_term = _clamp(deduction_depth / _DEPTH_SATURATION)
    hypothesis_term = _clamp(hypothesis_depth / _HYPOTHESIS_SATURATION)
    # branching ranges roughly 1..size; map that onto 0..1.
    branching_term = _clamp((branching_factor - 1.0) / max(size - 1, 1))
    sparsity_term = _clamp(1.0 - clue_count / max(size * size, 1))
    variety_term = _clamp(clue_variety)

    score = (
        _W_DEPTH * depth_term
        + _W_HYPOTHESIS * hypothesis_term
        + _W_BRANCHING * branching_term
        + _W_SPARSITY * sparsity_term
        + _W_VARIETY * variety_term
    )
    return _clamp(score, 0.0, 1.0) * 10.0


__all__ = ["composite_difficulty"]
