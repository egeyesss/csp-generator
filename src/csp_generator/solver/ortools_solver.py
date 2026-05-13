"""OR-Tools (CP-SAT) constraint model for zebra-style logic puzzles.

This module is the "truth oracle" side of the architecture: it answers
*satisfiability*, *uniqueness*, and *what is the solution* — fast and
reliably — without any pretense of mimicking human reasoning. The companion
custom propagation tracer (added separately) handles the human-deduction
analytics.

Variable scheme
---------------
For each (category, value) pair, we create one IntVar in [0, size-1] whose
value is the *position* that value occupies. Per-category AllDifferent forces
each category to be a permutation of its value pool. Clues are then translated
into arithmetic constraints over these position variables. This formulation is
compact (size*num_categories vars) and lets relational clues become simple
algebra on the variables.
"""

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from csp_generator.models import (
    AbsolutePosition,
    Adjacency,
    Clue,
    Conditional,
    Disjunction,
    NegativeAssociation,
    PositiveAssociation,
    Puzzle,
    RelativePosition,
    Solution,
    Theme,
)


@dataclass(frozen=True)
class _BuiltModel:
    model: cp_model.CpModel
    # pos[category][value] -> position IntVar
    pos: dict[str, dict[str, cp_model.IntVar]]


def _validate_clue_refs(clue: Clue, theme: Theme) -> None:
    """Fail fast if a clue references categories or values not in the theme."""

    def check(category: str, value: str) -> None:
        if category not in theme.attributes:
            raise ValueError(f"clue references unknown category {category!r}")
        if value not in theme.attributes[category]:
            raise ValueError(f"clue references unknown value {value!r} in category {category!r}")

    if isinstance(clue, PositiveAssociation | NegativeAssociation | Adjacency | RelativePosition):
        check(clue.category_a, clue.value_a)
        check(clue.category_b, clue.value_b)
    elif isinstance(clue, AbsolutePosition):
        check(clue.category, clue.value)
        if clue.position >= theme.size:
            raise ValueError(f"clue position {clue.position} out of range for size {theme.size}")
    elif isinstance(clue, Disjunction):
        check(clue.category_a, clue.value_a)
        for opt_category, opt_value in clue.options:
            check(opt_category, opt_value)
    elif isinstance(clue, Conditional):
        check(clue.if_category_a, clue.if_value_a)
        check(clue.if_category_b, clue.if_value_b)
        check(clue.then_category_a, clue.then_value_a)
        check(clue.then_category_b, clue.then_value_b)


def _apply_clue(
    model: cp_model.CpModel,
    pos: dict[str, dict[str, cp_model.IntVar]],
    clue: Clue,
) -> None:
    if isinstance(clue, PositiveAssociation):
        model.add(pos[clue.category_a][clue.value_a] == pos[clue.category_b][clue.value_b])
    elif isinstance(clue, NegativeAssociation):
        model.add(pos[clue.category_a][clue.value_a] != pos[clue.category_b][clue.value_b])
    elif isinstance(clue, AbsolutePosition):
        model.add(pos[clue.category][clue.value] == clue.position)
    elif isinstance(clue, Adjacency):
        a = pos[clue.category_a][clue.value_a]
        b = pos[clue.category_b][clue.value_b]
        # |a - b| == 1 — encode as a disjunction of two linear constraints
        # using two reified booleans tied by add_bool_or.
        left = model.new_bool_var("adj_left")
        right = model.new_bool_var("adj_right")
        model.add(a - b == 1).only_enforce_if(left)
        model.add(a - b != 1).only_enforce_if(~left)
        model.add(b - a == 1).only_enforce_if(right)
        model.add(b - a != 1).only_enforce_if(~right)
        model.add_bool_or([left, right])
    elif isinstance(clue, RelativePosition):
        model.add(pos[clue.category_a][clue.value_a] < pos[clue.category_b][clue.value_b])
    elif isinstance(clue, Disjunction):
        # At least one of the options must coincide with (category_a, value_a).
        target = pos[clue.category_a][clue.value_a]
        option_holds: list[cp_model.IntVar] = []
        for i, (opt_category, opt_value) in enumerate(clue.options):
            b = model.new_bool_var(f"disj_{i}")
            model.add(target == pos[opt_category][opt_value]).only_enforce_if(b)
            model.add(target != pos[opt_category][opt_value]).only_enforce_if(~b)
            option_holds.append(b)
        model.add_bool_or(option_holds)
    elif isinstance(clue, Conditional):
        ant = model.new_bool_var("cond_ant")
        cons = model.new_bool_var("cond_cons")
        if_a = pos[clue.if_category_a][clue.if_value_a]
        if_b = pos[clue.if_category_b][clue.if_value_b]
        then_a = pos[clue.then_category_a][clue.then_value_a]
        then_b = pos[clue.then_category_b][clue.then_value_b]
        model.add(if_a == if_b).only_enforce_if(ant)
        model.add(if_a != if_b).only_enforce_if(~ant)
        model.add(then_a == then_b).only_enforce_if(cons)
        model.add(then_a != then_b).only_enforce_if(~cons)
        model.add_implication(ant, cons)
    else:  # pragma: no cover - exhaustive over the Clue union
        raise NotImplementedError(f"no constraint translation for {type(clue).__name__}")


def _build(puzzle: Puzzle, theme: Theme) -> _BuiltModel:
    if puzzle.theme_id != theme.id:
        raise ValueError(
            f"puzzle.theme_id {puzzle.theme_id!r} does not match theme.id {theme.id!r}"
        )
    if puzzle.size != theme.size:
        raise ValueError(f"puzzle.size {puzzle.size} does not match theme.size {theme.size}")

    model = cp_model.CpModel()
    pos: dict[str, dict[str, cp_model.IntVar]] = {}
    for category, values in theme.attributes.items():
        pos[category] = {
            value: model.new_int_var(0, theme.size - 1, f"{category}::{value}") for value in values
        }
        model.add_all_different(list(pos[category].values()))

    for clue in puzzle.clues:
        _validate_clue_refs(clue, theme)
        _apply_clue(model, pos, clue)

    return _BuiltModel(model=model, pos=pos)


class _SolutionRecorder(cp_model.CpSolverSolutionCallback):
    """Count solutions up to a cap, optionally keeping the first."""

    def __init__(
        self,
        pos: dict[str, dict[str, cp_model.IntVar]],
        limit: int,
        record_first: bool,
    ) -> None:
        super().__init__()
        self._pos = pos
        self._limit = limit
        self._record_first = record_first
        self.count = 0
        self.first_assignments: dict[str, list[str]] | None = None

    def on_solution_callback(self) -> None:
        if self._record_first and self.first_assignments is None:
            assignments: dict[str, list[str]] = {}
            for category, by_value in self._pos.items():
                size = len(by_value)
                slots: list[str | None] = [None] * size
                for value, var in by_value.items():
                    slots[int(self.value(var))] = value
                assignments[category] = [v for v in slots if v is not None]
            self.first_assignments = assignments
        self.count += 1
        if self.count >= self._limit:
            self.stop_search()


def count_solutions(puzzle: Puzzle, theme: Theme, limit: int = 2) -> int:
    """Count solutions of `puzzle` under `theme`, stopping after `limit`.

    Returns `min(actual_count, limit)`. Use `limit=2` for a uniqueness check —
    that's all we ever need to distinguish "no solution / unique / ambiguous".
    """
    if limit < 1:
        raise ValueError(f"limit must be >= 1, got {limit}")
    built = _build(puzzle, theme)
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = True
    recorder = _SolutionRecorder(built.pos, limit=limit, record_first=False)
    solver.solve(built.model, recorder)
    return recorder.count


def is_uniquely_solvable(puzzle: Puzzle, theme: Theme) -> bool:
    """True iff the puzzle has exactly one solution under `theme`."""
    return count_solutions(puzzle, theme, limit=2) == 1


def solve(puzzle: Puzzle, theme: Theme) -> Solution | None:
    """Return one solution, or None if the puzzle is unsatisfiable.

    Does not check uniqueness — use `is_uniquely_solvable` for that.
    """
    built = _build(puzzle, theme)
    solver = cp_model.CpSolver()
    solver.parameters.enumerate_all_solutions = False
    recorder = _SolutionRecorder(built.pos, limit=1, record_first=True)
    solver.solve(built.model, recorder)
    if recorder.first_assignments is None:
        return None
    return Solution(theme_id=theme.id, assignments=recorder.first_assignments)
