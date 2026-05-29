"""CLI entry point for csp-generator."""

from __future__ import annotations

import click

from csp_generator import __version__
from csp_generator.cli.export import export_cmd
from csp_generator.cli.generate import generate_cmd
from csp_generator.cli.review import review_cmd
from csp_generator.cli.stats import stats_cmd


@click.group()
@click.version_option(__version__, prog_name="csp-generator")
def main() -> None:
    """CSP-based zebra-style logic puzzle generator."""


main.add_command(generate_cmd, name="generate")
main.add_command(review_cmd, name="review")
main.add_command(export_cmd, name="export")
main.add_command(stats_cmd, name="stats")


if __name__ == "__main__":
    main()
