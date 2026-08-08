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


@dataclass(frozen=True)
class ResolutionCandidate:
    crop: CropLike
    score: float
    matched_alias: str


@dataclass(frozen=True)
class Resolution:
    normalized_text: str
    status: ResolutionStatus
    method: ResolutionMethod | None
    resolved_crop: CropLike | None
    candidates: tuple[ResolutionCandidate, ...]


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


def resolve_term(original_text: str, crops: Sequence[CropLike]) -> Resolution:
    normalized_text = normalize_term(original_text)
    if not normalized_text:
        return Resolution(
            normalized_text="",
            status=ResolutionStatus.UNRESOLVED,
            method=None,
            resolved_crop=None,
            candidates=(),
        )

    exact_matches: dict[str, CropLike] = {}
    exact_alias_by_crop: dict[str, str] = {}
    for crop in crops:
        for alias in {crop.canonical_name, *(item.alias for item in crop.aliases)}:
            if normalize_term(alias) == normalized_text:
                exact_matches[crop.id] = crop
                exact_alias_by_crop[crop.id] = alias

    if len(exact_matches) == 1:
        crop = next(iter(exact_matches.values()))
        candidate = ResolutionCandidate(
            crop=crop,
            score=1.0,
            matched_alias=exact_alias_by_crop[crop.id],
        )
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.RESOLVED,
            method=ResolutionMethod.EXACT_ALIAS,
            resolved_crop=crop,
            candidates=(candidate,),
        )

    if exact_matches:
        candidates = tuple(
            ResolutionCandidate(
                crop=crop,
                score=1.0,
                matched_alias=exact_alias_by_crop[crop.id],
            )
            for crop in sorted(
                exact_matches.values(),
                key=lambda item: item.canonical_name.casefold(),
            )
        )
        return Resolution(
            normalized_text=normalized_text,
            status=ResolutionStatus.NEEDS_CONFIRMATION,
            method=ResolutionMethod.EXACT_ALIAS,
            resolved_crop=None,
            candidates=candidates,
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

    return Resolution(
        normalized_text=normalized_text,
        status=ResolutionStatus.UNRESOLVED,
        method=None,
        resolved_crop=None,
        candidates=(),
    )
