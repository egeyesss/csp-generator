"""Theme loader behavior."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from csp_generator.models import Theme
from csp_generator.themes import ThemeNotFoundError, available_themes, load_theme


def test_classic_houses_is_available() -> None:
    assert "classic_houses" in available_themes()


def test_load_classic_houses() -> None:
    theme = load_theme("classic_houses")
    assert theme.id == "classic_houses"
    assert theme.size == 5
    assert set(theme.categories) == {"color", "nationality", "drink", "pet", "cigarette"}
    assert "zebra" in theme.attributes["pet"]


def test_classic_houses_question_target() -> None:
    theme = load_theme("classic_houses")
    assert theme.question_target == ("pet", "zebra")


def test_question_target_invalid_category_raises() -> None:
    with pytest.raises(ValidationError):
        Theme(
            id="t",
            name="T",
            entity_label="house",
            attributes={"color": ["red", "blue"]},
            question_target=("nonexistent", "red"),
        )


def test_question_target_invalid_value_raises() -> None:
    with pytest.raises(ValidationError):
        Theme(
            id="t",
            name="T",
            entity_label="house",
            attributes={"color": ["red", "blue"]},
            question_target=("color", "purple"),
        )


def test_load_unknown_theme_raises() -> None:
    with pytest.raises(ThemeNotFoundError):
        load_theme("does_not_exist")
