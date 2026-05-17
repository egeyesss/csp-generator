"""Constraint solvers.

Two solvers live here:

- `ortools_solver` — the truth oracle (CP-SAT). Answers uniqueness and finds a
  solution; opaque about reasoning steps.
- `propagator` — the custom propagation tracer. Mirrors human deduction to
  measure deduction depth and the case-analysis a puzzle needs.
"""

from csp_generator.solver.ortools_solver import (
    count_solutions,
    is_uniquely_solvable,
    solve,
)
from csp_generator.solver.propagator import DeductionTrace, trace

__all__ = [
    "DeductionTrace",
    "count_solutions",
    "is_uniquely_solvable",
    "solve",
    "trace",
]
