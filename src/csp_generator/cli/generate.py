"""Implementation of the `generate` CLI command."""

from __future__ import annotations

import random
from pathlib import Path

import click

from csp_generator.generator.pipeline import generate as _generate
from csp_generator.themes.loader import ThemeNotFoundError, available_themes, load_theme


@click.command("generate")
@click.option(
    "--theme",
    "theme_id",
    default="classic_houses",
    show_default=True,
    help=f"Theme to generate puzzles for. Available: {', '.join(available_themes())}",
)
@click.option("--count", default=1, show_default=True, help="Number of puzzles to generate.")
@click.option("--seed", default=None, type=int, help="RNG seed for reproducible output.")
@click.option(
    "--restarts",
    default=10,
    show_default=True,
    help="Greedy-removal restart count. Higher → smaller clue sets, slower.",
)
@click.option(
    "--output-dir",
    default="output/candidates",
    show_default=True,
    help="Directory to write puzzle JSON files.",
)
@click.option(
    "--min-difficulty",
    default=None,
    type=float,
    help=(
        "Reject puzzles whose composite_difficulty falls below this floor; "
        "retry up to --max-retries per candidate. Returns best effort if "
        "the floor is unreachable."
    ),
)
@click.option(
    "--max-retries",
    default=10,
    show_default=True,
    help="Retry budget per candidate when --min-difficulty is set.",
)
def generate_cmd(
    theme_id: str,
    count: int,
    seed: int | None,
    restarts: int,
    output_dir: str,
    min_difficulty: float | None,
    max_retries: int,
) -> None:
    """Generate candidate puzzles and write them to OUTPUT_DIR."""
    try:
        theme = load_theme(theme_id)
    except ThemeNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(seed)
    for i in range(count):
        puzzle = _generate(
            theme,
            rng=rng,
            n_restarts=restarts,
            min_difficulty=min_difficulty,
            max_retries=max_retries,
        )
        path = out / f"{puzzle.id}.json"
        path.write_text(puzzle.model_dump_json(indent=2), encoding="utf-8")
        difficulty = (
            f"{puzzle.metrics.composite_difficulty:.1f}"
            if puzzle.metrics and puzzle.metrics.composite_difficulty is not None
            else "?"
        )
        click.echo(
            f"[{i + 1}/{count}] {puzzle.id}  "
            f"clues={puzzle.metrics.clue_count if puzzle.metrics else '?'}  "
            f"difficulty={difficulty}  "
            f"→ {path}"
        )
