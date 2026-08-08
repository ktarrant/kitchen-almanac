from __future__ import annotations

from dataclasses import dataclass, field

from kitchen_almanac.services.wishlist_resolver import (
    ResolutionMethod,
    ResolutionStatus,
    normalize_term,
    resolve_term,
)


@dataclass
class Alias:
    alias: str


@dataclass
class Crop:
    id: str
    slug: str
    canonical_name: str
    aliases: list[Alias] = field(default_factory=list)


CROPS = [
    Crop("1", "fava-beans", "Fava Beans", [Alias("broad beans")]),
    Crop("2", "shell-beans", "Shell Beans", [Alias("shelling beans")]),
    Crop("3", "string-beans", "String Beans", [Alias("green beans")]),
    Crop("4", "tomatoes", "Tomatoes", [Alias("tomato")]),
]


def test_normalize_term_is_case_and_punctuation_insensitive() -> None:
    assert normalize_term("  Sugar-Snap PEAS! ") == "sugar snap peas"


def test_unique_alias_resolves_automatically() -> None:
    resolution = resolve_term("Tomato", CROPS)

    assert resolution.status == ResolutionStatus.RESOLVED
    assert resolution.method == ResolutionMethod.EXACT_ALIAS
    assert resolution.resolved_crop is not None
    assert resolution.resolved_crop.slug == "tomatoes"


def test_typo_requires_confirmation_instead_of_auto_resolving() -> None:
    resolution = resolve_term("tomatos", CROPS)

    assert resolution.status == ResolutionStatus.NEEDS_CONFIRMATION
    assert resolution.method == ResolutionMethod.FUZZY
    assert resolution.resolved_crop is None
    assert resolution.candidates[0].crop.slug == "tomatoes"


def test_broad_term_returns_stable_ambiguous_candidates() -> None:
    resolution = resolve_term("beans", CROPS)

    assert resolution.status == ResolutionStatus.NEEDS_CONFIRMATION
    assert [candidate.crop.slug for candidate in resolution.candidates] == [
        "fava-beans",
        "shell-beans",
        "string-beans",
    ]


def test_unknown_term_remains_unresolved() -> None:
    resolution = resolve_term("dragon fruit", CROPS)

    assert resolution.status == ResolutionStatus.UNRESOLVED
    assert resolution.resolved_crop is None
    assert resolution.candidates == ()
