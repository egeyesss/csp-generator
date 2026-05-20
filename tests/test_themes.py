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


# ---------------------------------------------------------------------------
# Multi-theme: office (5x5 Deep), dorm (5x5 Deep), restaurant (4x4 Coffee)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "theme_id,expected_size",
    [("office", 5), ("dorm", 5), ("restaurant", 4)],
)
def test_new_theme_loads(theme_id: str, expected_size: int) -> None:
    theme = load_theme(theme_id)
    assert theme.id == theme_id
    assert theme.size == expected_size


@pytest.mark.parametrize("theme_id", ["office", "dorm", "restaurant"])
def test_new_theme_declares_question_target(theme_id: str) -> None:
    theme = load_theme(theme_id)
    assert theme.question_target is not None
    cat, val = theme.question_target
    assert val in theme.attributes[cat]


@pytest.mark.parametrize("theme_id", ["office", "dorm", "restaurant"])
def test_new_theme_has_descriptors_for_all_categories(theme_id: str) -> None:
    theme = load_theme(theme_id)
    for category in theme.categories:
        assert (
            category in theme.descriptors
        ), f"{theme_id}: category {category!r} missing a descriptor"


def test_all_themes_available() -> None:
    available = set(available_themes())
    assert {"classic_houses", "office", "dorm", "restaurant"} <= available
