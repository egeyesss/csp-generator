"""Interactive review CLI for candidate puzzles.

The flow: a folder of candidate puzzle JSONs (output of `csp-generator
generate`) is walked one file at a time. For each candidate, the reviewer
sees the rendered grid, the clue list, and the difficulty metrics, then
decides whether to approve, reject, or skip. Approved and rejected puzzles
are moved into sibling folders along with a sidecar `<id>.review.json`
holding the structured review record; skipped puzzles stay put so the
session can be resumed later.

The session loop is parameterized on a `prompter` iterable so the Click +
Rich UI is just one of several drivers (the tests use a scripted prompter).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from csp_generator.clues.templates import render
from csp_generator.models import Puzzle, ReviewData, Theme
from csp_generator.themes.loader import ThemeNotFoundError, load_theme


@dataclass(frozen=True)
class ReviewDecision:
    """One reviewer's verdict on a single candidate.

    `skip=True` means the candidate is being deferred and should stay in
    the candidates folder; `review` may be None in that case.
    """

    review: ReviewData | None
    skip: bool = False


@dataclass(frozen=True)
class SessionResult:
    """Tally of a completed review session."""

    reviewed: int
    approved: int
    rejected: int
    skipped: int


def _load_puzzle(path: Path) -> Puzzle:
    return Puzzle.model_validate_json(path.read_text(encoding="utf-8"))


def _move_pair(puzzle_path: Path, sidecar_path: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    puzzle_path.replace(dest_dir / puzzle_path.name)
    sidecar_path.replace(dest_dir / sidecar_path.name)


def run_review_session(
    candidates_dir: Path,
    approved_dir: Path,
    rejected_dir: Path,
    prompter: Iterable[ReviewDecision],
) -> SessionResult:
    """Walk every candidate JSON in `candidates_dir` and route it by decision.

    For each candidate the next `ReviewDecision` is pulled from `prompter`.
    Approved/rejected candidates move into the matching destination folder
    along with a freshly written `<id>.review.json` sidecar. Skipped
    candidates stay in `candidates_dir`. Stray `.review.json` files in the
    candidates folder are ignored.
    """
    approved = rejected = skipped = 0
    iterator: Iterator[ReviewDecision] = iter(prompter)

    paths = sorted(p for p in candidates_dir.glob("*.json") if not p.name.endswith(".review.json"))
    for puzzle_path in paths:
        decision = next(iterator)
        if decision.skip:
            skipped += 1
            continue
        if decision.review is None:
            raise ValueError(f"non-skip decision for {puzzle_path.name} has no ReviewData attached")

        sidecar_path = puzzle_path.with_name(f"{puzzle_path.stem}.review.json")
        sidecar_path.write_text(decision.review.model_dump_json(indent=2), encoding="utf-8")

        dest = approved_dir if decision.review.approved else rejected_dir
        _move_pair(puzzle_path, sidecar_path, dest)
        if decision.review.approved:
            approved += 1
        else:
            rejected += 1

    return SessionResult(
        reviewed=approved + rejected,
        approved=approved,
        rejected=rejected,
        skipped=skipped,
    )


# ---------------------------------------------------------------------------
# Rich rendering
# ---------------------------------------------------------------------------


def _grid_table(puzzle: Puzzle, theme: Theme) -> Table:
    """A position-major grid of the puzzle's solution, one row per category."""
    table = Table(title=f"{theme.name} — solution", show_lines=False)
    table.add_column("category", style="bold cyan")
    for pos in range(theme.size):
        table.add_column(f"{theme.position_label} {pos + 1}", justify="center")

    solution = puzzle.solution
    if solution is None:
        table.add_row("(no solution attached)", *(["?"] * theme.size))
        return table
    for category in theme.categories:
        row = [category] + [solution.value_at(category, pos) for pos in range(theme.size)]
        table.add_row(*row)
    return table


def _clues_panel(puzzle: Puzzle, theme: Theme) -> Panel:
    lines = [f"{i + 1}. {render(c, theme)}" for i, c in enumerate(puzzle.clues)]
    return Panel("\n".join(lines), title=f"clues ({len(puzzle.clues)})", border_style="blue")


def _metrics_line(puzzle: Puzzle) -> str:
    m = puzzle.metrics
    if m is None:
        return "metrics: (not computed)"
    pieces = [
        f"clues={m.clue_count}",
        f"depth={m.deduction_depth}",
        f"hypothesis={m.hypothesis_depth}",
        f"branching={m.branching_factor:.2f}" if m.branching_factor is not None else "branching=?",
        f"variety={m.clue_variety:.2f}" if m.clue_variety is not None else "variety=?",
        (
            f"difficulty={m.composite_difficulty:.1f}/10"
            if m.composite_difficulty is not None
            else "difficulty=?"
        ),
    ]
    return "  ".join(pieces)


def _display_candidate(
    console: Console, puzzle: Puzzle, theme: Theme, index: int, total: int
) -> None:
    console.rule(f"[bold]candidate {index}/{total}[/bold]  {puzzle.id}")
    if puzzle.question is not None:
        cat, val = puzzle.question
        console.print(f"[bold yellow]question:[/bold yellow] who has {cat}={val}?")
    console.print(_grid_table(puzzle, theme))
    console.print(_clues_panel(puzzle, theme))
    console.print(_metrics_line(puzzle))


def _interactive_prompter(console: Console, candidates_dir: Path) -> Iterator[ReviewDecision]:
    """Yield decisions by asking the human reviewer through Rich prompts.

    Themes are loaded lazily on the file the loop is currently displaying,
    so we re-read each candidate's puzzle here just to know its theme. The
    session loop reads it again to do the actual work — duplicate but cheap.
    """
    paths = sorted(p for p in candidates_dir.glob("*.json") if not p.name.endswith(".review.json"))
    for i, puzzle_path in enumerate(paths, start=1):
        puzzle = _load_puzzle(puzzle_path)
        try:
            theme = load_theme(puzzle.theme_id)
        except ThemeNotFoundError:
            console.print(
                f"[red]skipping {puzzle_path.name}: theme {puzzle.theme_id!r} not found[/red]"
            )
            yield ReviewDecision(review=None, skip=True)
            continue

        _display_candidate(console, puzzle, theme, i, len(paths))
        action = Prompt.ask(
            "[bold]action[/bold]",
            choices=["approve", "reject", "skip"],
            default="approve",
        )
        if action == "skip":
            yield ReviewDecision(review=None, skip=True)
            continue

        approved = action == "approve"
        difficulty = IntPrompt.ask("difficulty 1-10", default=5)
        difficulty = max(1, min(10, difficulty))
        variety = IntPrompt.ask("clue variety 1-5", default=3)
        variety = max(1, min(5, variety))
        aha = IntPrompt.ask("aha factor 1-5", default=3)
        aha = max(1, min(5, aha))
        notes = Prompt.ask("notes (optional)", default="")
        rejection_reason: str | None = None
        if not approved:
            rejection_reason = Prompt.ask("rejection reason", default="not specified")

        yield ReviewDecision(
            review=ReviewData(
                approved=approved,
                difficulty_rating=difficulty,
                clue_variety_rating=variety,
                aha_factor=aha,
                notes=notes,
                rejection_reason=rejection_reason,
            ),
            skip=False,
        )

        if not Confirm.ask("continue to next candidate?", default=True):
            break


@click.command("review")
@click.option(
    "--candidates-dir",
    default="output/candidates",
    show_default=True,
    help="Directory holding candidate puzzle JSONs.",
)
@click.option(
    "--approved-dir",
    default="output/approved",
    show_default=True,
    help="Where to move approved puzzles + their review sidecars.",
)
@click.option(
    "--rejected-dir",
    default="output/rejected",
    show_default=True,
    help="Where to move rejected puzzles + their review sidecars.",
)
def review_cmd(
    candidates_dir: str,
    approved_dir: str,
    rejected_dir: str,
    *,
    _stream: TextIO | None = None,  # test seam, unused at runtime
) -> None:
    """Interactively review candidate puzzles and move them by verdict."""
    candidates = Path(candidates_dir)
    if not candidates.is_dir():
        raise click.ClickException(f"candidates directory {candidates} does not exist")

    approved = Path(approved_dir)
    rejected = Path(rejected_dir)
    approved.mkdir(parents=True, exist_ok=True)
    rejected.mkdir(parents=True, exist_ok=True)

    console = Console()
    candidate_files = [p for p in candidates.glob("*.json") if not p.name.endswith(".review.json")]
    if not candidate_files:
        console.print(f"[yellow]no candidates found in {candidates}[/yellow]")
        return

    result = run_review_session(
        candidates_dir=candidates,
        approved_dir=approved,
        rejected_dir=rejected,
        prompter=_interactive_prompter(console, candidates),
    )
    console.print(
        f"[bold green]done.[/bold green] reviewed {result.reviewed} "
        f"(approved {result.approved}, rejected {result.rejected}, "
        f"skipped {result.skipped})"
    )


__all__ = ["ReviewDecision", "SessionResult", "review_cmd", "run_review_session"]
