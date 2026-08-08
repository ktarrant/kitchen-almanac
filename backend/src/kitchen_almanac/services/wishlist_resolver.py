from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum
from typing import Protocol


class CropAliasLike(Protocol):
    alias: str


class CropLike(Protocol):
    id: str
    slug: str
    canonical_name: str
    aliases: Sequence[CropAliasLike]


class CultivarLike(Protocol):
    id: str
    slug: str
    canonical_name: str
    crop_type: str | None
    crop: CropLike
    aliases: Sequence[CropAliasLike]


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    NEEDS_CONFIRMATION = "needs_confirmation"
    UNRESOLVED = "unresolved"
    CUSTOM = "custom"


class ResolutionMethod(StrEnum):
    EXACT_ALIAS = "exact_alias"
    FUZZY = "fuzzy"
    USER_CONFIRMED = "user_confirmed"
    CUSTOM = "custom"
    EXACT_CULTIVAR_ALIAS = "exact_cultivar_alias"
    FUZZY_CULTIVAR = "fuzzy_cultivar"
    CROP_TYPE = "crop_type"


class IntentKind(StrEnum):
    CROP = "crop"
    CULTIVAR = "cultivar"
    CROP_TYPE = "crop_type"


@dataclass(frozen=True)
class ResolutionCandidate:
    crop: CropLike
    score: float
    matched_alias: str


@dataclass(frozen=True)
class CultivarResolutionCandidate:
    cultivar: CultivarLike
    score: float
    matched_alias: str


@dataclass(frozen=True)
class Resolution:
    normalized_text: str
    status: ResolutionStatus
    method: ResolutionMethod | None
    resolved_crop: CropLike | None
    candidates: tuple[ResolutionCandidate, ...]
    intent_kind: IntentKind = IntentKind.CROP
    cultivar_intent_text: str | None = None
    crop_type_intent: str | None = None
    resolved_cultivar: CultivarLike | None = None
    cultivar_candidates: tuple[CultivarResolutionCandidate, ...] = ()


def normalize_term(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold().replace("&", " and ")
    value = re.sub(r"[^\w\s]", " ", value)
    return " ".join(value.replace("_", " ").split())


def _similarity(query: str, alias: str) -> float:
    ratio = SequenceMatcher(None, query, alias).ratio()
    query_tokens = query.split()
    alias_tokens = alias.split()
    token_ratio = SequenceMatcher(
        None,
        " ".join(sorted(query_tokens)),
        " ".join(sorted(alias_tokens)),
    ).ratio()

    # A whole crop word such as "beans" or "peas" should surface the relevant
    # compound crop names, but only for confirmation. This never auto-resolves.
    subset_score = 0.0
    if (
        len(query_tokens) == 1
        and len(query_tokens[0]) >= 4
        and query_tokens[0] in alias_tokens
        and len(alias_tokens) > 1
    ):
        subset_score = 0.76

    return max(ratio, token_ratio, subset_score)


def _best_candidate(query: str, crop: CropLike) -> ResolutionCandidate:
    aliases = {crop.canonical_name, *(alias.alias for alias in crop.aliases)}
    scored_aliases = [
        (_similarity(query, normalized), alias)
        for alias in aliases
        if (normalized := normalize_term(alias))
    ]
    score, alias = max(scored_aliases, key=lambda item: (item[0], item[1].casefold()))
    return ResolutionCandidate(crop=crop, score=round(score, 4), matched_alias=alias)


def _best_cultivar_candidate(
    query: str,
    cultivar: CultivarLike,
) -> CultivarResolutionCandidate:
    aliases = {cultivar.canonical_name, *(alias.alias for alias in cultivar.aliases)}
    scored_aliases = [
        (_similarity(query, normalized), alias)
        for alias in aliases
        if (normalized := normalize_term(alias))
    ]
    score, alias = max(scored_aliases, key=lambda item: (item[0], item[1].casefold()))
    return CultivarResolutionCandidate(
        cultivar=cultivar,
        score=round(score, 4),
        matched_alias=alias,
    )


def _exact_crop_matches(query: str, crops: Sequence[CropLike]) -> tuple[ResolutionCandidate, ...]:
    matches: dict[str, ResolutionCandidate] = {}
    for crop in crops:
        for alias in {crop.canonical_name, *(item.alias for item in crop.aliases)}:
            if normalize_term(alias) == query:
                matches[crop.id] = ResolutionCandidate(crop=crop, score=1.0, matched_alias=alias)
    return tuple(sorted(matches.values(), key=lambda item: item.crop.canonical_name.casefold()))


def _exact_cultivar_matches(
    query: str,
    cultivars: Sequence[CultivarLike],
) -> tuple[CultivarResolutionCandidate, ...]:
    matches: dict[str, CultivarResolutionCandidate] = {}
    for cultivar in cultivars:
        for alias in {cultivar.canonical_name, *(item.alias for item in cultivar.aliases)}:
            if normalize_term(alias) == query:
                matches[cultivar.id] = CultivarResolutionCandidate(
                    cultivar=cultivar,
                    score=1.0,
                    matched_alias=alias,
                )
    return tuple(sorted(matches.values(), key=lambda item: item.cultivar.canonical_name.casefold()))


def _qualified_crop_intent(
    query: str,
    crops: Sequence[CropLike],
) -> tuple[CropLike, str] | None:
    matches: list[tuple[int, str, CropLike]] = []
    for crop in crops:
        for alias in {crop.canonical_name, *(item.alias for item in crop.aliases)}:
            normalized_alias = normalize_term(alias)
            suffix = f" {normalized_alias}"
            if query.endswith(suffix):
                intent = query[: -len(suffix)].strip()
                if intent:
                    matches.append((len(normalized_alias), intent, crop))
    if not matches:
        return None
    longest = max(length for length, _, _ in matches)
    best = {(intent, crop.id): crop for length, intent, crop in matches if length == longest}
    if len(best) != 1:
        return None
    (intent, _), crop = next(iter(best.items()))
    return crop, intent


def _cultivar_intent_resolution(
    *,
    normalized_text: str,
    intent: str,
    crop: CropLike,
    cultivars: Sequence[CultivarLike],
) -> Resolution:
    crop_cultivars = [cultivar for cultivar in cultivars if cultivar.crop.id == crop.id]
    exact = _exact_cultivar_matches(intent, crop_cultivars)
    if len(exact) == 1:
        cultivar = exact[0].cultivar
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.RESOLVED,
            method=ResolutionMethod.EXACT_CULTIVAR_ALIAS,
            resolved_crop=crop,
            candidates=(),
            intent_kind=IntentKind.CULTIVAR,
            cultivar_intent_text=intent,
            resolved_cultivar=cultivar,
            cultivar_candidates=exact,
        )
    if exact:
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.NEEDS_CONFIRMATION,
            method=ResolutionMethod.EXACT_CULTIVAR_ALIAS,
            resolved_crop=crop,
            candidates=(),
            intent_kind=IntentKind.CULTIVAR,
            cultivar_intent_text=intent,
            cultivar_candidates=exact,
        )

    intent_tokens = set(intent.split())
    type_matches = tuple(
        CultivarResolutionCandidate(
            cultivar=cultivar,
            score=1.0 if normalize_term(cultivar.crop_type or "") == intent else 0.9,
            matched_alias=(cultivar.crop_type or "").replace("_", " "),
        )
        for cultivar in sorted(crop_cultivars, key=lambda item: item.canonical_name.casefold())
        if intent_tokens
        and intent_tokens.issubset(set(normalize_term(cultivar.crop_type or "").split()))
    )
    if type_matches:
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.NEEDS_CONFIRMATION,
            method=ResolutionMethod.CROP_TYPE,
            resolved_crop=crop,
            candidates=(),
            intent_kind=IntentKind.CROP_TYPE,
            cultivar_intent_text=intent,
            crop_type_intent=intent,
            cultivar_candidates=type_matches,
        )

    fuzzy = sorted(
        (_best_cultivar_candidate(intent, cultivar) for cultivar in crop_cultivars),
        key=lambda item: (-item.score, item.cultivar.canonical_name.casefold()),
    )
    fuzzy_candidates = tuple(candidate for candidate in fuzzy if candidate.score >= 0.72)[:3]
    if fuzzy_candidates:
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.NEEDS_CONFIRMATION,
            method=ResolutionMethod.FUZZY_CULTIVAR,
            resolved_crop=crop,
            candidates=(),
            intent_kind=IntentKind.CULTIVAR,
            cultivar_intent_text=intent,
            cultivar_candidates=fuzzy_candidates,
        )
    return Resolution(
        normalized_text=normalized_text,
        status=ResolutionStatus.UNRESOLVED,
        method=None,
        resolved_crop=crop,
        candidates=(),
        intent_kind=IntentKind.CULTIVAR,
        cultivar_intent_text=intent,
    )


def resolve_term(
    original_text: str,
    crops: Sequence[CropLike],
    cultivars: Sequence[CultivarLike] = (),
) -> Resolution:
    normalized_text = normalize_term(original_text)
    if not normalized_text:
        return Resolution(
            normalized_text="",
            status=ResolutionStatus.UNRESOLVED,
            method=None,
            resolved_crop=None,
            candidates=(),
        )

    exact_matches = _exact_crop_matches(normalized_text, crops)
    if len(exact_matches) == 1:
        candidate = exact_matches[0]
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.RESOLVED,
            method=ResolutionMethod.EXACT_ALIAS,
            resolved_crop=candidate.crop,
            candidates=(candidate,),
        )

    if exact_matches:
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.NEEDS_CONFIRMATION,
            method=ResolutionMethod.EXACT_ALIAS,
            resolved_crop=None,
            candidates=exact_matches,
        )

    exact_cultivars = _exact_cultivar_matches(normalized_text, cultivars)
    if len(exact_cultivars) == 1:
        candidate = exact_cultivars[0]
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.RESOLVED,
            method=ResolutionMethod.EXACT_CULTIVAR_ALIAS,
            resolved_crop=candidate.cultivar.crop,
            candidates=(),
            intent_kind=IntentKind.CULTIVAR,
            cultivar_intent_text=normalized_text,
            resolved_cultivar=candidate.cultivar,
            cultivar_candidates=(candidate,),
        )
    if exact_cultivars:
        crop_ids = {candidate.cultivar.crop.id for candidate in exact_cultivars}
        resolved_crop = exact_cultivars[0].cultivar.crop if len(crop_ids) == 1 else None
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.NEEDS_CONFIRMATION,
            method=ResolutionMethod.EXACT_CULTIVAR_ALIAS,
            resolved_crop=resolved_crop,
            candidates=(),
            intent_kind=IntentKind.CULTIVAR,
            cultivar_intent_text=normalized_text,
            cultivar_candidates=exact_cultivars,
        )

    qualified = _qualified_crop_intent(normalized_text, crops)
    if qualified is not None:
        crop, intent = qualified
        return _cultivar_intent_resolution(
            normalized_text=normalized_text,
            intent=intent,
            crop=crop,
            cultivars=cultivars,
        )

    candidates = sorted(
        (_best_candidate(normalized_text, crop) for crop in crops),
        key=lambda item: (-item.score, item.crop.canonical_name.casefold()),
    )
    fuzzy_candidates = tuple(candidate for candidate in candidates if candidate.score >= 0.72)[:3]
    if fuzzy_candidates:
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.NEEDS_CONFIRMATION,
            method=ResolutionMethod.FUZZY,
            resolved_crop=None,
            candidates=fuzzy_candidates,
        )

    fuzzy_cultivars = sorted(
        (_best_cultivar_candidate(normalized_text, cultivar) for cultivar in cultivars),
        key=lambda item: (-item.score, item.cultivar.canonical_name.casefold()),
    )
    cultivar_candidates = tuple(
        candidate for candidate in fuzzy_cultivars if candidate.score >= 0.72
    )[:3]
    if cultivar_candidates:
        crop_ids = {candidate.cultivar.crop.id for candidate in cultivar_candidates}
        resolved_crop = cultivar_candidates[0].cultivar.crop if len(crop_ids) == 1 else None
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.NEEDS_CONFIRMATION,
            method=ResolutionMethod.FUZZY_CULTIVAR,
            resolved_crop=resolved_crop,
            candidates=(),
            intent_kind=IntentKind.CULTIVAR,
            cultivar_intent_text=normalized_text,
            cultivar_candidates=cultivar_candidates,
        )

    return Resolution(
        normalized_text=normalized_text,
        status=ResolutionStatus.UNRESOLVED,
        method=None,
        resolved_crop=None,
        candidates=(),
    )
