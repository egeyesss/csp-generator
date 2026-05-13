"""Theme loader behavior."""

from __future__ import annotations

import pytest

from csp_generator.themes import ThemeNotFoundError, available_themes, load_theme


def test_classic_houses_is_available() -> None:
    assert "classic_houses" in available_themes()


def test_load_classic_houses() -> None:
    theme = load_theme("classic_houses")
    assert theme.id == "classic_houses"
    assert theme.size == 5
    assert set(theme.categories) == {"color", "nationality", "drink", "pet", "cigarette"}
    assert "zebra" in theme.attributes["pet"]


def test_load_unknown_theme_raises() -> None:
    with pytest.raises(ThemeNotFoundError):
        load_theme("does_not_exist")
