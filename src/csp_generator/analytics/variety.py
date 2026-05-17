"""Clue-variety scoring.

A puzzle that leans on one clue type feels monotonous; a good mix reads as
more elegant. We measure the *evenness* of the clue-type distribution with
Pielou's index — the Shannon entropy of the type mix normalised by its
maximum for the number of distinct types present.

The score is in ``[0, 1]``: 0 when every clue is the same type (or there are
none), 1 when the types present are used in equal proportion. It rewards a
balanced mix; the composite difficulty score factors in clue count
separately.
"""

from __future__ import annotations

import math
from collections import Counter

from csp_generator.models import Clue


def clue_variety(clues: list[Clue]) -> float:
    """Pielou evenness of the clue-type distribution, in ``[0, 1]``."""
    if not clues:
        return 0.0
    counts = Counter(clue.type for clue in clues)
    distinct = len(counts)
    if distinct == 1:
        return 0.0
    total = len(clues)
    entropy = -sum((n / total) * math.log2(n / total) for n in counts.values())
    return entropy / math.log2(distinct)


__all__ = ["clue_variety"]
