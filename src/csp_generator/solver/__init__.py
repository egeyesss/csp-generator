"""Constraint solvers.

Two solvers live here:

- `ortools_solver` — the truth oracle (CP-SAT). Answers uniqueness and finds a
  solution; opaque about reasoning steps.
- A custom propagation tracer — will be added alongside the analytics layer to
  measure deduction depth.
"""

from csp_generator.solver.ortools_solver import (
    count_solutions,
    is_uniquely_solvable,
    solve,
)

__all__ = ["count_solutions", "is_uniquely_solvable", "solve"]
