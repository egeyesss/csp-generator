"""Load themes from packaged YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from csp_generator.models import Theme

_THEMES_DIR = Path(__file__).parent / "data"


class ThemeNotFoundError(LookupError):
    """Raised when a requested theme id has no matching YAML file."""


def themes_dir() -> Path:
    return _THEMES_DIR


def available_themes() -> list[str]:
    """Sorted list of theme ids that ship with the package."""
    return sorted(path.stem for path in _THEMES_DIR.glob("*.yaml"))


def load_theme(theme_id: str) -> Theme:
    """Load and validate the theme named `theme_id` from the packaged YAML."""
    path = _THEMES_DIR / f"{theme_id}.yaml"
    if not path.is_file():
        raise ThemeNotFoundError(
            f"theme {theme_id!r} not found in {_THEMES_DIR} " f"(available: {available_themes()})"
        )
    with path.open("r", encoding="utf-8") as fh:
        raw: Any = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"theme file {path} must contain a YAML mapping at the top level")
    return Theme.model_validate(raw)
