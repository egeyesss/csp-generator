"""Natural-language rendering of clues against a theme.

Each clue type maps to a fixed English sentence pattern; the noun and verb
phrases that fill in the template come from the theme's per-category
`descriptors`. Each category can declare a `subject` noun phrase (e.g.
``"the {value} drinker"``) and optionally a `predicate` verb phrase
(``"drinks {value}"``).

The result is sentences like:

    The Englishman lives in the red house.    (PA, color has a predicate)
    The dog owner smokes Chesterfields.       (PA, cigarette has a predicate)
    Alice is the engineer.                    (PA, role has a predicate)
    The Norwegian is in house 1.              (AbsolutePosition)
    The Chesterfields smoker is next to the fox owner.  (Adjacency)

When neither side of a PositiveAssociation declares a predicate, rendering
falls back to a copula form (``X is Y``). Categories without a descriptor at
all fall back to a generic ``"the {value} ({category})"`` phrase — readable
but obviously placeholder-shaped, which is intentional so test themes don't
silently look like real ones.
"""

from __future__ import annotations

from csp_generator.models import (
    AbsolutePosition,
    Adjacency,
    CategoryDescriptor,
    Clue,
    Conditional,
    Disjunction,
    ImmediateLeftOf,
    NegativeAssociation,
    PositiveAssociation,
    RelativePosition,
    Theme,
)

_FALLBACK_SUBJECT = "the {value} ({category})"


def _subject_template(theme: Theme, category: str) -> str:
    descriptor = theme.descriptors.get(category)
    if descriptor is None:
        return _FALLBACK_SUBJECT
    if isinstance(descriptor, CategoryDescriptor):
        return descriptor.subject
    return descriptor


def _predicate_template(theme: Theme, category: str) -> str | None:
    descriptor = theme.descriptors.get(category)
    if isinstance(descriptor, CategoryDescriptor):
        return descriptor.predicate
    return None


def _subject(theme: Theme, category: str, value: str) -> str:
    return _subject_template(theme, category).format(value=value, category=category)


def _predicate(theme: Theme, category: str, value: str) -> str | None:
    template = _predicate_template(theme, category)
    if template is None:
        return None
    return template.format(value=value, category=category)


def _is_location(theme: Theme, category: str) -> bool:
    descriptor = theme.descriptors.get(category)
    return isinstance(descriptor, CategoryDescriptor) and descriptor.is_location


def _subject_predicate_split(
    theme: Theme, cat_a: str, val_a: str, cat_b: str, val_b: str
) -> tuple[str, str, str]:
    """Pick the subject side for a PA/NA between (cat_a, val_a) and (cat_b, val_b).

    Returns (subject_text, predicate_category, predicate_value). When exactly
    one side is a location category, the other side is the subject — so we get
    "The Englishman lives in the red house" rather than "The red house is the
    Englishman". Otherwise the side appearing first in `theme.attributes`
    insertion order is the subject; themes control voice by ordering their
    YAML categories.
    """
    a_is_loc = _is_location(theme, cat_a)
    b_is_loc = _is_location(theme, cat_b)
    if a_is_loc and not b_is_loc:
        subj_cat, subj_val = cat_b, val_b
        pred_cat, pred_val = cat_a, val_a
    elif b_is_loc and not a_is_loc:
        subj_cat, subj_val = cat_a, val_a
        pred_cat, pred_val = cat_b, val_b
    else:
        cats = theme.categories
        if cats.index(cat_a) <= cats.index(cat_b):
            subj_cat, subj_val = cat_a, val_a
            pred_cat, pred_val = cat_b, val_b
        else:
            subj_cat, subj_val = cat_b, val_b
            pred_cat, pred_val = cat_a, val_a
    return _subject(theme, subj_cat, subj_val), pred_cat, pred_val


def _join_options(theme: Theme, options: list[tuple[str, str]]) -> str:
    return ", ".join(_subject(theme, c, v) for c, v in options)


def _capitalize_first(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _render_pa_body(theme: Theme, cat_a: str, val_a: str, cat_b: str, val_b: str) -> str:
    """Render a PA-shaped clause (uncapitalized, no trailing punctuation).

    Used by PositiveAssociation directly and by Conditional for both its
    antecedent and consequent.
    """
    subject, pred_cat, pred_val = _subject_predicate_split(theme, cat_a, val_a, cat_b, val_b)
    predicate = _predicate(theme, pred_cat, pred_val)
    if predicate is not None:
        return f"{subject} {predicate}"
    return f"{subject} is {_subject(theme, pred_cat, pred_val)}"


def render(clue: Clue, theme: Theme) -> str:
    """Render a clue to a single English sentence under the given theme."""
    if isinstance(clue, PositiveAssociation):
        body = _render_pa_body(theme, clue.category_a, clue.value_a, clue.category_b, clue.value_b)
        return _capitalize_first(f"{body}.")
    if isinstance(clue, NegativeAssociation):
        subject, pred_cat, pred_val = _subject_predicate_split(
            theme, clue.category_a, clue.value_a, clue.category_b, clue.value_b
        )
        return _capitalize_first(f"{subject} is not {_subject(theme, pred_cat, pred_val)}.")
    if isinstance(clue, AbsolutePosition):
        subj = _subject(theme, clue.category, clue.value)
        return _capitalize_first(f"{subj} is in {theme.position_label} {clue.position + 1}.")
    if isinstance(clue, Adjacency):
        a = _subject(theme, clue.category_a, clue.value_a)
        b = _subject(theme, clue.category_b, clue.value_b)
        return _capitalize_first(f"{a} is next to {b}.")
    if isinstance(clue, RelativePosition):
        a = _subject(theme, clue.category_a, clue.value_a)
        b = _subject(theme, clue.category_b, clue.value_b)
        return _capitalize_first(f"{a} is somewhere to the left of {b}.")
    if isinstance(clue, ImmediateLeftOf):
        a = _subject(theme, clue.category_a, clue.value_a)
        b = _subject(theme, clue.category_b, clue.value_b)
        return _capitalize_first(f"{a} is directly to the left of {b}.")
    if isinstance(clue, Disjunction):
        a = _subject(theme, clue.category_a, clue.value_a)
        opts = _join_options(theme, clue.options)
        return _capitalize_first(f"{a} is paired with one of: {opts}.")
    if isinstance(clue, Conditional):
        if_body = _render_pa_body(
            theme,
            clue.if_category_a,
            clue.if_value_a,
            clue.if_category_b,
            clue.if_value_b,
        )
        then_body = _render_pa_body(
            theme,
            clue.then_category_a,
            clue.then_value_a,
            clue.then_category_b,
            clue.then_value_b,
        )
        return _capitalize_first(f"if {if_body}, then {then_body}.")
    raise NotImplementedError(  # pragma: no cover - exhaustive over the Clue union
        f"no renderer for {type(clue).__name__}"
    )
