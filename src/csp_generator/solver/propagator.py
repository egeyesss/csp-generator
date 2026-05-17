"""Custom propagation tracer — the deduction-depth half of the two solvers.

OR-Tools answers *whether* a puzzle is uniquely solvable but says nothing
about how hard the reasoning is. This tracer mirrors a human solving by pure
deduction.

Two layers of reasoning, both sound:

1. **Propagation waves.** Repeatedly apply every clue's rule plus
   AllDifferent until nothing more changes. The number of waves is the
   ``deduction_depth``.
2. **Contradiction-driven case analysis.** Zebra-style puzzles (the Einstein
   riddle included) aren't solvable by propagation alone. When propagation
   stalls, hypothesise a candidate, propagate on a clone, and if it forces a
   contradiction the candidate is *provably* impossible and is eliminated —
   exactly the "if it were here, then… contradiction, so it isn't" move a
   human makes. The deepest nesting of such case analysis needed is the
   ``hypothesis_depth``: 0 means plain propagation sufficed, higher means the
   puzzle demands harder look-ahead.

A puzzle that can't be fully resolved even with bounded case analysis is
flagged ``requires_guess`` — research-grade puzzles must be pure-deduction.
"""

from __future__ import annotations

from dataclasses import dataclass

from csp_generator.clues.propagation import propagate
from csp_generator.clues.state import PossibilityState
from csp_generator.models import Clue, Puzzle, Theme

# Monotone state (rules only ever remove candidates) guarantees a fixpoint;
# this cap turns a hypothetical buggy rule into a loud failure, not a hang.
_MAX_WAVES = 1000

# How deep nested case analysis may go. Phase 2 uses iterative deepening —
# it always tries the shallowest look-ahead first and only escalates when
# genuinely stuck — so well-formed puzzles (Einstein, minimal 5x5) resolve at
# nesting 1 in milliseconds and never pay for the deeper, exponential levels.
# A puzzle still unresolved at this cap is treated as not pure-deduction.
_MAX_HYPOTHESIS_DEPTH = 3


@dataclass(frozen=True)
class DeductionTrace:
    """Outcome of tracing a puzzle by pure deduction.

    ``deduction_depth`` is the number of propagation waves on the real grid
    (initial pass plus the re-propagation triggered by each proven
    elimination). ``hypothesis_depth`` is the deepest nesting of
    contradiction-driven case analysis required (0 = propagation alone).
    ``question_target_wave`` is the wave the answer cell resolved on, or
    ``None`` if there is no target / it never resolved. ``state`` is the
    final knowledge state so callers can read the deduced grid.
    """

    deduction_depth: int
    hypothesis_depth: int
    solved: bool
    requires_guess: bool
    question_target_wave: int | None
    state: PossibilityState


def _all_different_closure(state: PossibilityState, theme: Theme) -> bool:
    """Apply AllDifferent once: pin a position only one value can take, and a
    value with only one position left."""
    changed = False
    for category, values in theme.attributes.items():
        for position in range(theme.size):
            candidates = [v for v in values if state.is_possible(category, v, position)]
            if len(candidates) == 1:
                changed |= state.pin(category, candidates[0], position)
        for value in values:
            positions = state.possible(category, value)
            if len(positions) == 1:
                changed |= state.pin(category, value, next(iter(positions)))
    return changed


def _one_wave(state: PossibilityState, clues: list[Clue], theme: Theme) -> bool:
    """One pass of every clue rule plus AllDifferent. True iff anything moved."""
    changed = False
    for clue in clues:
        changed |= propagate(clue, state)
    changed |= _all_different_closure(state, theme)
    return changed


def _propagate(state: PossibilityState, clues: list[Clue], theme: Theme) -> None:
    """Run propagation waves until a fixpoint (or a contradiction)."""
    for _ in range(_MAX_WAVES):
        if not _one_wave(state, clues, theme) or state.contradiction():
            return
    raise AssertionError("propagation did not reach a fixpoint")


def _ordered_unresolved(state: PossibilityState, theme: Theme) -> list[tuple[str, str]]:
    """Unresolved cells, most-constrained first — refutations tend to fall
    out faster on cells with the fewest candidates left."""
    cells = [
        (category, value)
        for category, values in theme.attributes.items()
        for value in values
        if state.resolved_position(category, value) is None
    ]
    cells.sort(key=lambda cv: len(state.possible(*cv)))
    return cells


def _refute(state: PossibilityState, clues: list[Clue], theme: Theme, depth: int) -> bool:
    """True iff `state` is provably inconsistent within `depth` nested levels
    of case analysis. ``depth == 0`` means propagation only. Mutates the
    (clone) state; only proven-impossible candidates are ever removed, so a
    True result is a sound refutation."""
    _propagate(state, clues, theme)
    if state.contradiction():
        return True
    if state.is_resolved() or depth <= 0:
        return False

    progress = True
    while progress and not state.is_resolved():
        progress = False
        for cell in _ordered_unresolved(state, theme):
            for position in list(state.possible(*cell)):
                twin = state.clone()
                twin.pin(*cell, position)
                if _refute(twin, clues, theme, depth - 1):
                    state.eliminate(*cell, position)
                    _propagate(state, clues, theme)
                    if state.contradiction():
                        return True
                    progress = True
            if progress:
                break
    return False


def trace(puzzle: Puzzle, theme: Theme) -> DeductionTrace:
    """Solve `puzzle` by pure deduction and report how deep it went."""
    if puzzle.theme_id != theme.id:
        raise ValueError(
            f"puzzle.theme_id {puzzle.theme_id!r} does not match theme.id {theme.id!r}"
        )

    state = PossibilityState.from_theme(theme)
    clues = puzzle.clues
    target = puzzle.question or theme.question_target

    depth = 0
    target_wave: int | None = None

    def note_target() -> None:
        nonlocal target_wave
        if (
            target_wave is None
            and target is not None
            and state.resolved_position(*target) is not None
        ):
            target_wave = depth

    # Phase 1: plain propagation on the real grid, counting waves.
    for _ in range(_MAX_WAVES):
        if not _one_wave(state, clues, theme):
            break
        depth += 1
        note_target()
        if state.contradiction():
            break
    else:
        raise AssertionError("propagation did not reach a fixpoint")

    # Phase 2: when propagation stalls, refute impossible candidates via
    # case analysis. Iterative deepening — always try the shallowest
    # look-ahead first and only go deeper when a full scan finds nothing —
    # keeps well-formed puzzles at nesting 1 and avoids the exponential cost
    # of the deep levels unless a puzzle genuinely needs them.
    hypothesis_depth = 0
    look = 0
    while look < _MAX_HYPOTHESIS_DEPTH and not state.is_resolved() and not state.contradiction():
        made_progress = False
        for cell in _ordered_unresolved(state, theme):
            for position in list(state.possible(*cell)):
                twin = state.clone()
                twin.pin(*cell, position)
                if _refute(twin, clues, theme, look):
                    state.eliminate(*cell, position)
                    hypothesis_depth = max(hypothesis_depth, look + 1)
                    for _ in range(_MAX_WAVES):
                        if not _one_wave(state, clues, theme):
                            break
                        depth += 1
                        note_target()
                    made_progress = True
            if made_progress:
                break
        # Cheap eliminations may have reopened simpler deductions; restart
        # shallow. Only escalate nesting when a whole scan refuted nothing.
        look = 0 if made_progress else look + 1

    solved = state.is_resolved() and not state.contradiction()
    return DeductionTrace(
        deduction_depth=depth,
        hypothesis_depth=hypothesis_depth,
        solved=solved,
        requires_guess=not solved,
        question_target_wave=target_wave,
        state=state,
    )


__all__ = ["DeductionTrace", "trace"]
