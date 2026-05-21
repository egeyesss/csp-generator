# csp-generator

A constraint-programming generator for zebra-style logic puzzles. Builds uniquely-solvable puzzles, scores them by simulated human deduction, and ships them as JSON for downstream apps to consume.

[![CI](https://github.com/egeyesss/csp-generator/actions/workflows/ci.yml/badge.svg)](https://github.com/egeyesss/csp-generator/actions/workflows/ci.yml)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## What it does

Generates puzzles in the shape of the classic [zebra puzzle](https://en.wikipedia.org/wiki/Zebra_Puzzle) — a grid of N positions, each with N attributes drawn from K categories (e.g. nationality, drink, pet, color, cigarette), and a set of clues that uniquely pin down the assignment. The generator handles end-to-end:

- Random valid solutions, given a theme.
- A pool of every clue that's true under that solution, across seven clue types.
- A near-minimum subset of clues that still leaves the solution uniquely deducible.
- Difficulty analytics — deduction depth, branching factor, clue-type variety, composite score.
- An interactive review CLI for human curation of the candidate output.

Two grid sizes ship configured: 5×5 ("Deep") and 4×4 ("Coffee"). Four themes ship by default: classic_houses, office, dorm, restaurant. Adding a theme is a single YAML file.

## Why it's interesting

**Two solvers, deliberately.** OR-Tools (CP-SAT) is fast and reliable at answering "does this puzzle have exactly one solution?" but opaque about *how* it gets there. A second engine — a custom propagation tracer — mirrors the way a human eliminates options wave by wave, and gives us the deduction-depth and branching analytics that the difficulty score is built on. OR-Tools is the truth oracle; the tracer is the analytics tool. They cross-check each other on every puzzle.

**Einstein-shaped output.** The reducer aims for the canonical [Einstein puzzle](https://en.wikipedia.org/wiki/Zebra_Puzzle) clue-type distribution — roughly 8 PositiveAssociation, 4 Adjacency, 2 AbsolutePosition, 1 ImmediateLeftOf, 0 RelativePosition — across both 5×5 and 4×4 grids. Without per-type caps the reducer collapses to a PA + ImmediateLeftOf monoculture; the selection layer enforces the ratios explicitly.

**Human-in-the-loop curation.** Generated puzzles land in `output/candidates/`. The `csp-generator review` CLI walks the directory, renders each puzzle with Rich, prompts for a structured review verdict (difficulty rating, variety, aha-factor, freeform notes), and files the puzzle into `approved/` or `rejected/` alongside a `<id>.review.json` sidecar. The review data is captured cleanly so that downstream generator tuning can consume it later.

## Quickstart

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
csp-generator --help
pytest
```

## Example

Generate a 5×5 classic-houses puzzle:

```bash
csp-generator generate --theme classic_houses --count 1
```

Sample output (seed 7):

```
17 clues, difficulty 4.5/10
Question: who owns the zebra?

 1. The tea drinker is adjacent to the dog owner.
 2. The red house is adjacent to the Spaniard.
 3. The tea drinker is adjacent to the Spaniard.
 4. The Ukrainian is adjacent to the Norwegian.
 5. The fox owner is at position 2.
 6. The snails owner is at position 1.
 7. The Japanese is directly to the left of the horse owner.
 8. The Chesterfields smoker is paired with the milk drinker.
 9. The water drinker is paired with the Englishman.
10. The tea drinker is paired with the Japanese.
11. The Old Gold smoker is paired with the water drinker.
12. The Parliaments smoker is paired with the coffee drinker.
13. The yellow house is paired with the Spaniard.
14. The Kools smoker is paired with the Ukrainian.
15. The Chesterfields smoker is paired with the red house.
16. The Kools smoker is paired with the blue house.
17. The green house is paired with the tea drinker.
```

I am aware that the language here does not sound natural and it will be fixed soon. "The Chesterfields smoker is paired with the red house." --> "The Chesterfields smoker lives in the red house."

Note that "zebra" never appears in the clues — the answer falls out by elimination over the four named pets. That's the original Einstein flavor.

The CLI also supports interactive review:

```bash
csp-generator review              # walk output/candidates/, prompt verdict on each
csp-generator export --out v1.json   # bundle approved puzzles for downstream use
```

## Project layout

```
src/csp_generator/
├── models.py              # Pydantic data models (Puzzle, Solution, Clue, Theme, ...)
├── themes/                # YAML theme definitions + loader
├── solver/                # OR-Tools wrapper + custom propagation tracer
├── clues/                 # Clue types, propagation rules, NL templates, enumeration
├── generator/             # Random solution generation + minimum-clue-set selection
├── analytics/             # Difficulty score, variety score, reference puzzle bank
├── export/                # JSON export
└── cli/                   # generate / review / export commands

tests/                     # pytest + Hypothesis property tests
output/                    # candidates / approved / rejected / exports
```

## Architecture in one paragraph

A theme defines categories and value pools. The generator picks a random valid solution, enumerates every clue true under that solution across seven clue types (PositiveAssociation, NegativeAssociation, AbsolutePosition, Adjacency, RelativePosition, ImmediateLeftOf, plus Disjunction/Conditional stubbed), then greedily reduces the pool down to a near-minimum subset that still solves uniquely under OR-Tools. Before greedy reduction, a sequence of "cap" passes shapes the clue-type distribution toward Einstein's ratios. The custom propagation tracer walks the surviving clue set wave-by-wave to compute deduction depth, branching factor, and composite difficulty. The output is a JSON puzzle plus a metrics blob, ready for human review.

## Contributing

Contributions welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for setup, the test workflow, and PR conventions. Some directions that need attention:

- **More themes.** Each theme is a single YAML file under `src/csp_generator/themes/data/`. The four shipping themes are decent but a wider library would help — sci-fi, fantasy, sports, anything with a natural N-of-each-attribute structure.
- **Enabling Conditional / Disjunction clues.** Both clue types are fully modeled and have OR-Tools translations, propagation rules, and renderers — but they're not yet enumerated, because enumeration is combinatorially large and needs a smart sampler. A working enumerator for either would unlock richer puzzles.
- **Difficulty bank recalibration.** The reference puzzle bank used by the analytics layer was calibrated against an earlier version of the generator. The boundaries between easy / medium / hard need re-fitting against the current distributions.
- **Web review UI.** The review CLI works but a small web frontend (FastAPI + a static page) would make curating a launch puzzle bank much faster.
- **Multi-language rendering.** Clue templates are English-only. The renderer is theme-agnostic but locale-agnostic too — adding a locale layer is mostly mechanical.

For smaller starter tasks, check the [good first issue](https://github.com/egeyesss/csp-generator/labels/good%20first%20issue) label.

## Development

```bash
ruff check . && ruff format .
mypy src
pytest                         # full suite, ~4 min
pytest tests/test_selection_quality.py    # the slower invariant tests
pytest --cov=csp_generator     # with coverage
```

Pre-commit hooks (ruff, ruff-format, mypy, basic hygiene) run on every commit. CI runs the same checks on every PR.

## License

[MIT](LICENSE)
