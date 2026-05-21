# Contributing to csp-generator

Thanks for thinking about contributing. This document covers the setup, the test loop, and the conventions the repo follows so that your PR has the smoothest possible path to merge.

## Setup

Requires Python 3.12.

```bash
git clone https://github.com/egeyesss/csp-generator.git
cd csp-generator
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Verify the install:

```bash
pytest
csp-generator --help
```

The full test suite takes ~4 minutes — most of that is the property-based and integration tests that actually generate puzzles end-to-end. For tight inner loops, run individual test files.

## Test loop

```bash
pytest                                       # full suite
pytest tests/test_clues.py                   # one file
pytest tests/test_clues.py::test_render_immediate_left_of   # one test
pytest -x                                    # stop on first failure
pytest --cov=csp_generator                   # with coverage
```

Two test categories worth knowing about:

- **`test_selection_quality.py`** — integration tests that generate real puzzles and assert structural invariants on the output (e.g. "no entity is over-pinned by PA clues", "ImmediateLeftOf appears at most once per puzzle"). These are the slowest tests, ~2 minutes alone, but they catch the kind of regression unit tests miss.
- **Property-based tests with Hypothesis** — scattered through the other files. They run on randomly sampled solutions and verify invariants like "no propagation rule can eliminate the true solution."

If you add a new clue type, a new theme, or a new selection pass, both layers usually need a test.

## Style

- `ruff check` and `ruff format` both run as pre-commit hooks. CI re-runs them on every PR.
- `mypy --strict` runs the same way. Type annotations are required on all new function signatures.
- Module and function docstrings explain *why* the code looks the way it does, not what each line does. Reach for a docstring when behavior is non-obvious, a constraint isn't visible locally, or a design tradeoff was made.
- Comments on individual lines should be rare. If a line needs a comment to understand it, consider whether the code itself can be clearer.

## Branch + commit conventions

- Branch off `main`. Name the branch after the feature, not a ticket number — e.g. `add-disjunction-enumerator`, `web-review-ui`, `recalibrate-difficulty-bank`.
- Commit messages should be in imperative mood ("Add foo", not "Added foo"). Subject under 70 characters. Body explains the *why* — what's the constraint, what was the tradeoff, what regression are you preventing. A teammate skimming `git log` should get the gist in five seconds.
- Don't squash locally before pushing; the squash-merge happens at merge time.
- PRs land via squash-merge into `main`, keeping the history one-commit-per-PR.

## PR conventions

- One logical change per PR. A bugfix and a refactor should be two PRs.
- The PR description should answer three questions: *what changed*, *why*, *how was it tested*. If the PR adds analytics or affects clue distributions, a before/after comparison is welcome.
- Sample data tables, distribution histograms, or screenshots for UI changes all help reviewers a lot.
- Address review comments by pushing a new commit to the branch (not by force-pushing) so the review thread stays coherent. Squash happens automatically at merge.

## Architecture notes for newcomers

Three layers worth understanding before changing anything significant:

1. **Models (`src/csp_generator/models.py`).** Every data structure is a Pydantic model. `Clue` is a discriminated union — each concrete clue type has a `type: Literal[...]` field that Pydantic uses to route validation and serialization. Adding a new clue type means touching the model, the OR-Tools constraint, the propagation rule, the NL template, the enumerator, and the selection priority. Each layer has its own dispatch on `isinstance(clue, ...)`.
2. **Solvers (`src/csp_generator/solver/`).** OR-Tools is the truth oracle for uniqueness; the custom propagation tracer walks the same clue set wave-by-wave to compute analytics. Every propagation rule must be **sound** — it may only eliminate positions that are genuinely impossible, never the true solution. There's a property-based test that enforces this across thousands of random clue applications.
3. **Selection (`src/csp_generator/generator/selection.py`).** The reducer is greedy with multi-restart, ordered by `_REMOVAL_PRIORITY`. A series of "cap" passes (`_cap_category_pas`, `_destack_pa`, `_cap_clue_count`) trim the pool *before* greedy gets a shot — these enforce structural invariants the reducer alone wouldn't preserve (e.g. clue-type ratios mirroring Einstein's puzzle).

The flow is: random solution → enumerate every valid clue → cap passes shape the pool → greedy reduces to a near-minimum subset → analytics walk the final clue set → JSON exports.

## What needs help

- More themes. Each theme is a single YAML file under `src/csp_generator/themes/data/`. Look at `office.yaml` or `dorm.yaml` for the shape.
- Enabling Conditional and Disjunction clues end-to-end. Both are modeled but not yet enumerated.
- Recalibrating the reference puzzle bank against the current generator output.
- Multi-language clue rendering.
- A web review UI to replace the CLI for batch curation sessions.

Smaller starter tasks are tagged [good first issue](https://github.com/egeyesss/csp-generator/labels/good%20first%20issue) when available.

## Code of conduct

By participating in this project, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).
