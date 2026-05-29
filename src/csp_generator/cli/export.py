"""Implementation of the `export` CLI command.

Reads a directory of approved puzzles (and their review sidecars) and writes a
single versioned JSON bundle a downstream consumer can load directly. Optional
`--theme` / `--size` filters narrow which puzzles ship.
"""

from __future__ import annotations

from pathlib import Path

import click

from csp_generator.export.builder import build_bundle_from_directory


@click.command("export")
@click.option(
    "--in",
    "input_dir",
    default="output/approved",
    show_default=True,
    help="Directory of approved puzzle JSONs (+ review sidecars).",
)
@click.option(
    "--out",
    "output_path",
    default="output/exports/bundle.json",
    show_default=True,
    help="Output bundle path. Parent directories are created if missing.",
)
@click.option(
    "--theme",
    "theme",
    multiple=True,
    help="Restrict the bundle to puzzles for the given theme id. Repeatable.",
)
@click.option(
    "--size",
    "size",
    multiple=True,
    type=int,
    help="Restrict the bundle to puzzles of the given grid size. Repeatable.",
)
def export_cmd(
    input_dir: str,
    output_path: str,
    theme: tuple[str, ...],
    size: tuple[int, ...],
) -> None:
    """Bundle approved puzzles into a versioned JSON file."""
    in_path = Path(input_dir)
    out_path = Path(output_path)

    bundle = build_bundle_from_directory(
        in_path,
        theme_filter=theme or None,
        size_filter=size or None,
        source=str(in_path),
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")

    click.echo(
        f"wrote {len(bundle.puzzles)} puzzles " f"(schema {bundle.schema_version}) → {out_path}"
    )
