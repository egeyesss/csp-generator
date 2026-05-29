"""Batch-generate candidate puzzles across one or more themes.

The launch-prep workflow: run this overnight, wake up to a pile of candidates
in `output/candidates/`, walk them with `csp-generator review`, ship the
approved set with `csp-generator export`.

Defaults are tuned for the launch bank:
- All shipping themes, 50 puzzles each (200 total across the four).
- Each theme picks up its own size-based difficulty floor from the pipeline
  (currently 3.5 for 4x4), so 4x4 candidates skip the trivial cluster.
- Restarts default to the pipeline's own default (10) — higher would help
  minimality at the cost of significantly longer wall time.

Example:
    python -m scripts.batch_generate --per-theme 50
    python -m scripts.batch_generate --themes classic_houses,office --per-theme 25
"""

from __future__ import annotations

import random
from pathlib import Path

import click

from csp_generator.generator.pipeline import generate
from csp_generator.themes.loader import available_themes, load_theme


def run_batch(
    themes: list[str],
    per_theme: int,
    output_dir: Path,
    seed: int | None,
    restarts: int,
) -> dict[str, int]:
    """Generate `per_theme` candidates for each theme; write them under `output_dir`.

    Returns a count-per-theme summary. A bad theme id raises
    `ThemeNotFoundError` from the loader rather than silently producing no
    output for that theme.

    Each theme gets its own RNG stream keyed on `(seed, theme_id)`. That way
    `--seed 0 --themes classic_houses` produces the same classic_houses puzzles
    as `--seed 0 --themes restaurant,classic_houses` — re-running one theme
    after a review cycle doesn't depend on the rest of the bank's theme list
    staying frozen. When `seed` is None the streams are fresh on every run.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, int] = {}

    for theme_id in themes:
        theme = load_theme(theme_id)
        theme_rng = random.Random(f"{seed}:{theme_id}") if seed is not None else random.Random()
        for _ in range(per_theme):
            puzzle = generate(theme, rng=theme_rng, n_restarts=restarts)
            (output_dir / f"{puzzle.id}.json").write_text(
                puzzle.model_dump_json(indent=2), encoding="utf-8"
            )
        summary[theme_id] = per_theme

    return summary


def _parse_themes(value: str | None) -> list[str]:
    if not value:
        return list(available_themes())
    return [t.strip() for t in value.split(",") if t.strip()]


@click.command()
@click.option(
    "--themes",
    "themes_csv",
    default=None,
    help="Comma-separated theme ids. Defaults to every theme that ships.",
)
@click.option(
    "--per-theme",
    default=50,
    show_default=True,
    type=click.IntRange(min=1),
    help="Candidates to generate per theme.",
)
@click.option(
    "--output-dir",
    default="output/candidates",
    show_default=True,
    help="Where to write candidate JSONs (defaults to the review CLI's input dir).",
)
@click.option(
    "--seed",
    default=None,
    type=int,
    help="RNG seed for reproducible runs.",
)
@click.option(
    "--restarts",
    default=10,
    show_default=True,
    type=click.IntRange(min=1),
    help="Greedy-reduction restart count passed through to the pipeline.",
)
def main(
    themes_csv: str | None,
    per_theme: int,
    output_dir: str,
    seed: int | None,
    restarts: int,
) -> None:
    """Generate a batch of candidate puzzles for the launch bank."""
    themes = _parse_themes(themes_csv)
    out = Path(output_dir)

    click.echo(f"generating {per_theme} per theme across {len(themes)} themes → {out}")
    summary = run_batch(
        themes=themes,
        per_theme=per_theme,
        output_dir=out,
        seed=seed,
        restarts=restarts,
    )

    total = sum(summary.values())
    click.echo("")
    click.echo(f"done. wrote {total} candidates:")
    for theme_id, count in summary.items():
        click.echo(f"  {theme_id:<20} {count}")


if __name__ == "__main__":
    main()
