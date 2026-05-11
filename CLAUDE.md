# csp-generator — Project Instructions

Project-specific guidance for Claude. Global rules in `~/.claude/CLAUDE.md` still apply.

## What this project is

A research-grade CSP-based generator for zebra-style logic-grid puzzles. Built as the upstream content tool for the Zebra daily-puzzle web app (separate repo, built after this one).

Two reference notes in the user's Obsidian vault drive the spec:
- `/Users/egeyesilyurt/Documents/Claude Code/projects/zebra/generator-implementation.md` — the 6-week plan (authoritative)
- `/Users/egeyesilyurt/Documents/Claude Code/projects/zebra/zebra-brief.md` — the product brief (why this matters)

When in doubt about scope, defer to the implementation plan. Treat it as a contract.

## Architecture rules

- **Two solvers, on purpose.** OR-Tools is the *truth oracle* (uniqueness, satisfiability). The custom propagation tracer is the *analytics engine* (deduction depth, branching factor). They must agree on satisfiability — that's a property test. Don't merge them.
- **Pydantic for all data models.** `Puzzle`, `Solution`, `Clue`, `Theme`, `ReviewData`, `GenerationMetrics`. Validate at boundaries.
- **Themes are data, not code.** Add a new theme by dropping a YAML in `src/csp_generator/themes/data/` — never by branching on theme strings in clue templates.
- **CLI only.** No web UI in this repo. Web review tooling is explicitly out-of-scope; revisit only if manual review becomes the bottleneck.

## Code style

- Python 3.12, strict mypy, ruff (line-length 100). All three must be clean before commit.
- Type-annotate everything. `disallow_untyped_defs = true` is on.
- Test critical paths: solver, clue translation, selection, propagator. Target ≥80% coverage on those four.
- Hypothesis property tests for solver and clue invariants (see plan's Testing strategy section).

## Workflow

- Feature branches only; never commit to `main`. Plan milestones map naturally to branches: `week-1-foundations`, `week-2-clues`, etc.
- Commit messages: imperative tense, concern-scoped. `Co-Authored-By: Claude` lines are forbidden per global rules.
- Don't skip pre-commit hooks. If they fail, fix the underlying issue — never `--no-verify`.

## What NOT to do in this repo

- Don't add a web framework, server, or HTTP endpoints. This is a CLI tool.
- Don't add ML/auto-tuning of the generator from review data. That's v1.1+; for now, just *capture* the review data cleanly.
- Don't add multi-language clue rendering. English only.
- Don't add real-time / on-demand generation. Offline batch only.
