"""Mutable knowledge state for the custom propagation tracer.

The OR-Tools solver tells us *whether* a puzzle is uniquely solvable but is
opaque about the reasoning. To grade difficulty we model a human solver's
evolving knowledge explicitly: for every ``(category, value)`` cell, the set
of positions it could still occupy. Clue propagation rules narrow these sets;
the wave-loop driver iterates them to a fixpoint and counts the steps, which
is the deduction-depth signal.

This module is just the state primitive. The per-clue rules live in
``propagation.py`` and the wave loop in the solver package.
"""

from __future__ import annotations

from csp_generator.models import Theme

Cell = tuple[str, str]


class PossibilityState:
    """Per-cell candidate positions, with AllDifferent baked into ``pin``.

    ``size`` is the grid size (number of positions). A fresh state allows
    every value to be at every position; propagation only ever removes
    candidates, so the state moves monotonically toward a solution (or a
    contradiction).
    """

    def __init__(self, attributes: dict[str, list[str]]) -> None:
        if not attributes:
            raise ValueError("attributes must declare at least one category")
        self._size = len(next(iter(attributes.values())))
        self._categories: dict[str, list[str]] = {
            category: list(values) for category, values in attributes.items()
        }
        self._possible: dict[Cell, set[int]] = {
            (category, value): set(range(self._size))
            for category, values in attributes.items()
            for value in values
        }

    @classmethod
    def from_theme(cls, theme: Theme) -> PossibilityState:
        return cls(theme.attributes)

    def clone(self) -> PossibilityState:
        """A deep copy. The tracer explores hypotheticals on a clone so a
        contradiction there doesn't corrupt the real knowledge state."""
        twin = PossibilityState.__new__(PossibilityState)
        twin._size = self._size
        twin._categories = {cat: list(vals) for cat, vals in self._categories.items()}
        twin._possible = {cell: set(positions) for cell, positions in self._possible.items()}
        return twin

    @property
    def size(self) -> int:
        return self._size

    def possible(self, category: str, value: str) -> frozenset[int]:
        """The positions ``(category, value)`` could still occupy."""
        return frozenset(self._possible[(category, value)])

    def is_possible(self, category: str, value: str, position: int) -> bool:
        return position in self._possible[(category, value)]

    def eliminate(self, category: str, value: str, position: int) -> bool:
        """Drop ``position`` from a cell's candidates.

        Returns ``True`` iff the candidate set actually changed — the wave
        loop relies on this to detect when no further progress is possible.
        """
        cell = self._possible[(category, value)]
        if position not in cell:
            return False
        cell.discard(position)
        return True

    def pin(self, category: str, value: str, position: int) -> bool:
        """Fix ``(category, value)`` to ``position`` and apply AllDifferent.

        The value loses every other position, and every sibling value in the
        same category loses ``position``. Returns ``True`` iff anything
        changed; idempotent. If ``position`` was already eliminated for this
        cell the cell ends up empty — see :meth:`contradiction`.
        """
        changed = False
        for other_position in range(self._size):
            if other_position != position:
                changed |= self.eliminate(category, value, other_position)
        for sibling in self._categories[category]:
            if sibling != value:
                changed |= self.eliminate(category, sibling, position)
        return changed

    def resolved_position(self, category: str, value: str) -> int | None:
        """The fixed position of a cell, or ``None`` if still ambiguous."""
        cell = self._possible[(category, value)]
        if len(cell) == 1:
            return next(iter(cell))
        return None

    def is_resolved(self) -> bool:
        """True iff every cell has collapsed to exactly one position."""
        return all(len(positions) == 1 for positions in self._possible.values())

    def contradiction(self) -> bool:
        """True iff some cell has no candidate positions left."""
        return any(not positions for positions in self._possible.values())


__all__ = ["PossibilityState"]
