from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen_almanac.db_models import (
    Crop,
    Cultivar,
    CultivarDatasetVersion,
    DatasetVersion,
    GardenProfile,
)
from kitchen_almanac.schemas import (
    CatalogCropChoice,
    CatalogCropSearchResult,
    CatalogCultivarSearchResult,
    CatalogSearchResponse,
)
from kitchen_almanac.services.cultivar_service import list_cultivars
from kitchen_almanac.services.garden_profile_service import GardenProfileNotFoundError
from kitchen_almanac.services.suitability_service import assess_cultivar
from kitchen_almanac.services.wishlist_resolver import normalize_term

MINIMUM_FUZZY_SCORE = 0.64


class CatalogSearchUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class CropContext:
    crop: Crop
    intent: str
    matched_alias: str
    score: float


def _score(query: str, candidate: str) -> tuple[float, str]:
    normalized = normalize_term(candidate)
    if not normalized:
        return 0.0, "none"
    if query == normalized:
        return 1.0, "exact"
    if normalized.startswith(query):
        return 0.92, "prefix"
    if query in normalized:
        return 0.84, "contains"
    ratio = SequenceMatcher(None, query, normalized).ratio()
    token_ratio = SequenceMatcher(
        None,
        " ".join(sorted(query.split())),
        " ".join(sorted(normalized.split())),
    ).ratio()
    return round(max(ratio, token_ratio), 4), "fuzzy"


def _best_term(query: str, terms: set[str]) -> tuple[float, str, str]:
    scored = [(*_score(query, term), term) for term in terms]
    score, method, term = max(
        scored,
        key=lambda item: (item[0], item[1] == "exact", item[2].casefold()),
    )
    return score, method, term


def _crop_context(query: str, crops: list[Crop]) -> CropContext | None:
    contexts: list[CropContext] = []
    query_tokens = query.split()
    for crop in crops:
        aliases = {crop.canonical_name, *(alias.alias for alias in crop.aliases)}
        for alias in aliases:
            normalized_alias = normalize_term(alias)
            alias_length = len(normalized_alias.split())
            if len(query_tokens) < alias_length:
                continue
            suffix = " ".join(query_tokens[-alias_length:])
            suffix_score, _ = _score(suffix, normalized_alias)
            if suffix_score < 0.78:
                continue
            intent = " ".join(query_tokens[:-alias_length])
            contexts.append(
                CropContext(
                    crop=crop,
                    intent=intent,
                    matched_alias=alias,
                    score=suffix_score,
                )
            )
    if not contexts:
        return None
    contexts.sort(
        key=lambda item: (-item.score, -len(normalize_term(item.matched_alias)), item.crop.slug)
    )
    best = contexts[0]
    competing = {item.crop.id for item in contexts if item.score == best.score}
    return best if len(competing) == 1 else None


def search_catalog(
    session: Session,
    *,
    query: str,
    garden_profile_id: str,
) -> CatalogSearchResponse:
    profile = session.scalar(
        select(GardenProfile)
        .where(GardenProfile.id == garden_profile_id)
        .options(
            selectinload(GardenProfile.location_dataset),
            selectinload(GardenProfile.location_evidence),
        )
    )
    if profile is None:
        raise GardenProfileNotFoundError(garden_profile_id)
    crop_dataset = session.scalar(select(DatasetVersion).where(DatasetVersion.active.is_(True)))
    if crop_dataset is None:
        raise CatalogSearchUnavailableError("Load a crop catalog before searching.")

    normalized_query = normalize_term(query)
    crops = session.scalars(
        select(Crop)
        .where(Crop.dataset_version_id == crop_dataset.id)
        .options(selectinload(Crop.aliases))
        .order_by(Crop.canonical_name)
    ).all()
    context = _crop_context(normalized_query, crops)

    crop_results: dict[str, CatalogCropSearchResult] = {}
    for crop in crops:
        terms = {crop.canonical_name, *(alias.alias for alias in crop.aliases)}
        score, method, matched_alias = _best_term(normalized_query, terms)
        if score >= MINIMUM_FUZZY_SCORE:
            crop_results[crop.id] = CatalogCropSearchResult(
                crop=CatalogCropChoice(
                    slug=crop.slug,
                    canonical_name=crop.canonical_name,
                    planning_category=crop.planning_category,
                ),
                score=score,
                matched_alias=matched_alias,
                match_method=method,
            )
    if context is not None and context.crop.id not in crop_results:
        crop_results[context.crop.id] = CatalogCropSearchResult(
            crop=CatalogCropChoice(
                slug=context.crop.slug,
                canonical_name=context.crop.canonical_name,
                planning_category=context.crop.planning_category,
            ),
            score=round(0.8 * context.score, 4),
            matched_alias=context.matched_alias,
            match_method="crop_context",
        )
    exact_crop_ids = {
        crop_id for crop_id, result in crop_results.items() if result.match_method == "exact"
    }
    if exact_crop_ids:
        crop_results = {
            crop_id: result
            for crop_id, result in crop_results.items()
            if crop_id in exact_crop_ids
        }
    elif crop_results:
        best_crop_score = max(result.score for result in crop_results.values())
        crop_results = {
            crop_id: result
            for crop_id, result in crop_results.items()
            if result.score >= best_crop_score - 0.15
        }

    cultivar_dataset = session.scalar(
        select(CultivarDatasetVersion).where(
            CultivarDatasetVersion.active.is_(True),
            CultivarDatasetVersion.crop_dataset_version_id == crop_dataset.id,
        )
    )
    cultivar_results: list[CatalogCultivarSearchResult] = []
    if cultivar_dataset is not None:
        cultivars = session.scalars(
            select(Cultivar)
            .where(
                Cultivar.cultivar_dataset_version_id == cultivar_dataset.id,
                Cultivar.review_status == "approved",
            )
            .options(
                selectinload(Cultivar.aliases),
                selectinload(Cultivar.crop),
                selectinload(Cultivar.commercial_listings),
            )
        ).all()
        effective_query = context.intent if context is not None else normalized_query
        response_by_slug = {
            cultivar.slug: cultivar for cultivar in list_cultivars(session).cultivars
        }
        for cultivar in cultivars:
            if context is not None and cultivar.crop_id != context.crop.id:
                continue
            aliases = {
                cultivar.canonical_name,
                *(alias.alias for alias in cultivar.aliases),
            }
            score, method, matched_alias = _best_term(effective_query, aliases)
            type_text = (cultivar.crop_type or "").replace("_", " ")
            type_score, type_method = _score(effective_query, type_text)
            if set(effective_query.split()).issubset(set(normalize_term(type_text).split())):
                type_score = max(type_score, 0.88)
                type_method = "crop_type"
            listing_matches = [
                (*_score(normalized_query, listing.listing_name), listing.listing_name, listing)
                for listing in cultivar.commercial_listings
                if listing.review_status == "approved"
            ]
            listing_identifier_matches = [
                (
                    *_score(normalized_query, listing.source_identifier),
                    listing.source_identifier,
                    listing,
                )
                for listing in cultivar.commercial_listings
                if listing.review_status == "approved"
            ]
            listing_score, listing_method, listing_alias = 0.0, "none", ""
            if listing_matches or listing_identifier_matches:
                best_listing = max(
                    [*listing_matches, *listing_identifier_matches],
                    key=lambda item: (item[0], item[3].source_identifier),
                )
                listing_score = best_listing[0]
                listing_method = "commercial_listing"
                listing_alias = best_listing[2]
            if type_score > score:
                score, method, matched_alias = type_score, type_method, type_text
            if listing_score > score:
                score, method, matched_alias = listing_score, listing_method, listing_alias
            if context is not None and not effective_query:
                score, method, matched_alias = 0.7, "related_crop", context.matched_alias
            if score < MINIMUM_FUZZY_SCORE:
                continue
            cultivar_response = response_by_slug.get(cultivar.slug)
            if cultivar_response is None:
                continue
            cultivar_results.append(
                CatalogCultivarSearchResult(
                    cultivar=cultivar_response,
                    score=round(score, 4),
                    matched_alias=matched_alias,
                    match_method=method,
                    suitability=assess_cultivar(
                        profile,
                        cultivar_response,
                        cultivar_dataset_id=cultivar_dataset.id,
                    ),
                )
            )

    generic_crop_search = context is not None and not context.intent
    suitability_group_rank = {
        "best_documented_fit": 0,
        "other_documented": 1,
        "conditional": 2,
        "constrained": 3,
        "insufficient_evidence": 4,
    }

    def cultivar_sort_key(item: CatalogCultivarSearchResult):
        if generic_crop_search:
            return (
                suitability_group_rank[item.suitability.result_group],
                -(item.suitability.score if item.suitability.score is not None else -1),
                item.cultivar.canonical_name.casefold(),
            )
        return (-item.score, item.cultivar.canonical_name.casefold())

    return CatalogSearchResponse(
        query=query,
        normalized_query=normalized_query,
        crop_dataset_id=crop_dataset.id,
        cultivar_dataset_id=cultivar_dataset.id if cultivar_dataset else None,
        crop_choices=sorted(
            crop_results.values(),
            key=lambda item: (-item.score, item.crop.canonical_name.casefold()),
        )[:5],
        cultivars=sorted(
            cultivar_results,
            key=cultivar_sort_key,
        )[:12],
    )
