"""Implementation of the `stats` CLI command.

Walks a directory of puzzles, computes the bank summary, and prints a
Rich-rendered table.
"""

from __future__ import annotations

from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from csp_generator.analytics.stats import BankStats, Summary, compute_bank_stats

# Pydantic's int|float union deserializes ints losslessly; min/max can therefore
# be either type in memory. _fmt branches on that to render whole-number stats
# without a trailing ".0" — e.g. clue_count min as "7", not "7.0".


def _fmt(value: float | int | None, *, digits: int = 2) -> str:
    if value is None:
        return "-"
    if isinstance(value, int):
        return str(value)
    return f"{value:.{digits}f}"


def _render(stats: BankStats, console: Console) -> None:
    console.print(f"[bold]total puzzles:[/bold] {stats.total}")

    if stats.per_theme:
        theme_table = Table(title="per theme", show_header=True)
        theme_table.add_column("theme")
        theme_table.add_column("count", justify="right")
        for theme, count in sorted(stats.per_theme.items()):
            theme_table.add_row(theme, str(count))
        console.print(theme_table)

    if stats.per_size:
        size_table = Table(title="per size", show_header=True)
        size_table.add_column("size")
        size_table.add_column("count", justify="right")
        for size, count in sorted(stats.per_size.items()):
            size_table.add_row(str(size), str(count))
        console.print(size_table)

    metric_table = Table(title="metrics", show_header=True)
    metric_table.add_column("metric")
    metric_table.add_column("count", justify="right")
    metric_table.add_column("min", justify="right")
    metric_table.add_column("max", justify="right")
    metric_table.add_column("mean", justify="right")

    def _add(name: str, summary: Summary, *, digits: int = 2) -> None:
        metric_table.add_row(
            name,
            str(summary.count),
            _fmt(summary.min, digits=digits),
            _fmt(summary.max, digits=digits),
            _fmt(summary.mean, digits=digits),
        )

    _add("clue_count", stats.clue_count, digits=1)
    _add("deduction_depth", stats.deduction_depth, digits=1)
    _add("difficulty", stats.difficulty, digits=2)
    console.print(metric_table)


@click.command("stats")
@click.option(
    "--in",
    "input_dir",
    default="output/approved",
    show_default=True,
    help="Directory of puzzle JSONs to summarize.",
)
def stats_cmd(input_dir: str) -> None:
    """Summarize a directory of puzzles (counts per theme/size + metric ranges)."""
    try:
        stats = compute_bank_stats(Path(input_dir))
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    console = Console()
    _render(stats, console)
