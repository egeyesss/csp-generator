"""CLI entry point for csp-generator."""

from __future__ import annotations

import click

from csp_generator import __version__


@click.group()
@click.version_option(__version__, prog_name="csp-generator")
def main() -> None:
    """CSP-based zebra-style logic puzzle generator."""


@main.command()
def generate() -> None:
    """Generate candidate puzzles. (Stub — implemented in Week 3.)"""
    click.echo("generate: not implemented yet")


@main.command()
def review() -> None:
    """Interactively review candidate puzzles. (Stub — implemented in Week 5.)"""
    click.echo("review: not implemented yet")


@main.command()
def export() -> None:
    """Export approved puzzles to JSON. (Stub — implemented in Week 6.)"""
    click.echo("export: not implemented yet")


if __name__ == "__main__":
    main()
