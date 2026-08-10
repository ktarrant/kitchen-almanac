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


@dataclass
class Cultivar:
    id: str
    slug: str
    canonical_name: str
    crop_type: str | None
    crop: Crop
    aliases: list[Alias] = field(default_factory=list)


CROPS = [
    Crop("1", "fava-beans", "Fava Beans", [Alias("broad beans")]),
    Crop("2", "shell-beans", "Shell Beans", [Alias("shelling beans")]),
    Crop("3", "snap-beans", "Snap Beans", [Alias("green beans")]),
    Crop("4", "tomatoes", "Tomatoes", [Alias("tomato")]),
]

TOMATO = CROPS[-1]
CULTIVARS = [
    Cultivar(
        "c1",
        "san-marzano",
        "San Marzano",
        "paste_plum",
        TOMATO,
        [Alias("San Marzano")],
    ),
    Cultivar(
        "c2",
        "san-marzano-2",
        "San Marzano 2",
        "paste_plum",
        TOMATO,
        [Alias("San Marzano 2"), Alias("San Marzano II")],
    ),
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
        "snap-beans",
    ]


def test_unknown_term_remains_unresolved() -> None:
    resolution = resolve_term("dragon fruit", CROPS)

    assert resolution.status == ResolutionStatus.UNRESOLVED
    assert resolution.resolved_crop is None
    assert resolution.candidates == ()


def test_exact_cultivar_alias_resolves_without_losing_crop_identity() -> None:
    resolution = resolve_term("San Marzano II", CROPS, CULTIVARS)

    assert resolution.status == ResolutionStatus.RESOLVED
    assert resolution.method == ResolutionMethod.EXACT_CULTIVAR_ALIAS
    assert resolution.resolved_crop is TOMATO
    assert resolution.resolved_cultivar is CULTIVARS[1]
    assert resolution.cultivar_intent_text == "san marzano ii"


def test_crop_qualified_cultivar_resolves_and_preserves_original_intent() -> None:
    resolution = resolve_term("San Marzano tomatoes", CROPS, CULTIVARS)

    assert resolution.status == ResolutionStatus.RESOLVED
    assert resolution.resolved_crop is TOMATO
    assert resolution.resolved_cultivar is CULTIVARS[0]
    assert resolution.cultivar_intent_text == "san marzano"


def test_crop_type_intent_returns_cultivar_candidates_for_confirmation() -> None:
    resolution = resolve_term("paste tomato", CROPS, CULTIVARS)

    assert resolution.status == ResolutionStatus.NEEDS_CONFIRMATION
    assert resolution.method == ResolutionMethod.CROP_TYPE
    assert resolution.crop_type_intent == "paste"
    assert [candidate.cultivar.slug for candidate in resolution.cultivar_candidates] == [
        "san-marzano",
        "san-marzano-2",
    ]


def test_unknown_cultivar_intent_stays_linked_to_its_crop() -> None:
    resolution = resolve_term("Black Krim tomatoes", CROPS, CULTIVARS)

    assert resolution.status == ResolutionStatus.UNRESOLVED
    assert resolution.resolved_crop is TOMATO
    assert resolution.resolved_cultivar is None
    assert resolution.cultivar_intent_text == "black krim"


def test_cultivar_typo_requires_confirmation() -> None:
    resolution = resolve_term("San Marzno tomato", CROPS, CULTIVARS)

    assert resolution.status == ResolutionStatus.NEEDS_CONFIRMATION
    assert resolution.method == ResolutionMethod.FUZZY_CULTIVAR
    assert resolution.cultivar_candidates[0].cultivar.slug == "san-marzano"
