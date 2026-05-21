"""Natural-language rendering of clues against a theme.

Each clue type maps to a fixed sentence pattern; the noun phrases that fill in
the template come from the theme's per-category `descriptors`. A category
without a descriptor falls back to ``"the {value} ({category})"`` — enough to
keep tests and ad-hoc themes readable, ugly enough to encourage themes to
provide their own.

The phrasing here is intentionally semantically neutral ("paired with",
"adjacent to") rather than idiomatic per-category ("lives in", "owns",
"smokes"). Idiomatic phrasing per category arrives with the multi-theme
refactor; this version is correct, theme-agnostic, and stable enough for
downstream review tooling.
"""

from __future__ import annotations

from csp_generator.models import (
    AbsolutePosition,
    Adjacency,
    Clue,
    Conditional,
    Disjunction,
    ImmediateLeftOf,
    NegativeAssociation,
    PositiveAssociation,
    RelativePosition,
    Theme,
)

_FALLBACK_DESCRIPTOR = "the {value} ({category})"


def _noun(theme: Theme, category: str, value: str) -> str:
    """Render the noun phrase for `(category, value)` under `theme`."""
    template = theme.descriptors.get(category, _FALLBACK_DESCRIPTOR)
    return template.format(value=value, category=category)


def _join_options(theme: Theme, options: list[tuple[str, str]]) -> str:
    return ", ".join(_noun(theme, c, v) for c, v in options)


def _capitalize_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def render(clue: Clue, theme: Theme) -> str:
    """Render a clue to a single English sentence under the given theme."""
    if isinstance(clue, PositiveAssociation):
        a = _noun(theme, clue.category_a, clue.value_a)
        b = _noun(theme, clue.category_b, clue.value_b)
        return _capitalize_first(f"{a} is paired with {b}.")
    if isinstance(clue, NegativeAssociation):
        a = _noun(theme, clue.category_a, clue.value_a)
        b = _noun(theme, clue.category_b, clue.value_b)
        return _capitalize_first(f"{a} is not paired with {b}.")
    if isinstance(clue, AbsolutePosition):
        subj = _noun(theme, clue.category, clue.value)
        return _capitalize_first(f"{subj} is at position {clue.position + 1}.")
    if isinstance(clue, Adjacency):
        a = _noun(theme, clue.category_a, clue.value_a)
        b = _noun(theme, clue.category_b, clue.value_b)
        return _capitalize_first(f"{a} is adjacent to {b}.")
    if isinstance(clue, RelativePosition):
        a = _noun(theme, clue.category_a, clue.value_a)
        b = _noun(theme, clue.category_b, clue.value_b)
        return _capitalize_first(f"{a} is somewhere to the left of {b}.")
    if isinstance(clue, ImmediateLeftOf):
        a = _noun(theme, clue.category_a, clue.value_a)
        b = _noun(theme, clue.category_b, clue.value_b)
        return _capitalize_first(f"{a} is directly to the left of {b}.")
    if isinstance(clue, Disjunction):
        a = _noun(theme, clue.category_a, clue.value_a)
        opts = _join_options(theme, clue.options)
        return _capitalize_first(f"{a} is paired with one of: {opts}.")
    if isinstance(clue, Conditional):
        if_a = _noun(theme, clue.if_category_a, clue.if_value_a)
        if_b = _noun(theme, clue.if_category_b, clue.if_value_b)
        then_a = _noun(theme, clue.then_category_a, clue.then_value_a)
        then_b = _noun(theme, clue.then_category_b, clue.then_value_b)
        return _capitalize_first(
            f"if {if_a} is paired with {if_b}, then {then_a} is paired with {then_b}."
        )
    raise NotImplementedError(  # pragma: no cover - exhaustive over the Clue union
        f"no renderer for {type(clue).__name__}"
    )
