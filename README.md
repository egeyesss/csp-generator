# csp-generator

A CSP-based generator for zebra-style logic-grid puzzles, with rigorous difficulty analytics, multi-theme support, and a manual-review tooling layer.

Built as the upstream tool for the Zebra daily-puzzle web app: produces uniquely-solvable puzzles, scores their difficulty by simulated human deduction, and ships approved puzzles as JSON for the game to consume.

## Status

Pre-development scaffolding. See the [6-week implementation plan](docs/IMPLEMENTATION_PLAN.md) (TBA) for milestones.

## Why two solvers?

- **OR-Tools (CP-SAT)** is the truth oracle — answers "does this puzzle have exactly one solution?" fast and reliably.
- A **custom propagation tracer** mirrors human step-by-step deduction. OR-Tools is opaque about *how* it reaches its answer; the custom engine gives us deduction-depth, branching-factor, and other research-grade analytics.

They cross-check each other.

## Tech stack

- Python 3.12
- [OR-Tools](https://developers.google.com/optimization) (CP-SAT) — uniqueness verification + constraint satisfaction
- [Pydantic](https://docs.pydantic.dev) — data model validation
- [Click](https://click.palletsprojects.com) — CLI
- [Rich](https://rich.readthedocs.io) — terminal UI for the review CLI
- [PyYAML](https://pyyaml.org) — theme definitions
- [pytest](https://docs.pytest.org) + [Hypothesis](https://hypothesis.readthedocs.io) — testing
- [ruff](https://docs.astral.sh/ruff/) + [mypy](https://mypy-lang.org/) — lint + types

## Setup

Requires Python 3.12 and a POSIX shell.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

Verify the install:

```bash
csp-generator --help
pytest
```

## Usage

The CLI surface is built out across weeks 3–6. Once available:

```bash
# Generate a batch of candidate puzzles
csp-generator generate --theme classic_houses --size 5 --count 20

# Interactively review candidates
csp-generator review

# Bundle approved puzzles for the web app
csp-generator export --out output/exports/v1.json
```

## Project layout

```
src/csp_generator/
├── models.py              # Pydantic data models
├── themes/                # YAML theme definitions + loader
├── solver/                # OR-Tools wrapper + custom propagator
├── clues/                 # Clue types, templates, candidate generation
├── generator/             # Solution gen + minimum-clue-set selection
├── analytics/             # Difficulty, variety, solution-space metrics
├── export/                # JSON export for the web app
└── cli/                   # generate / review / export commands

tests/                     # pytest + Hypothesis
output/                    # candidates / approved / rejected / exports
```

## Development

```bash
ruff check . && ruff format .
mypy src
pytest --cov=csp_generator
```

Pre-commit hooks (ruff, ruff-format, mypy, basic hygiene) run on every commit.

## License

[MIT](LICENSE)
