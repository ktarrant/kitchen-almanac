from __future__ import annotations

from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen_almanac.db_models import (
    CommercialSeedListing,
    Cultivar,
    CultivarDatasetVersion,
    CultivarEvidenceClaim,
    CultivarSourceIdentifier,
)
from kitchen_almanac.schemas import (
    CatalogEvidenceSourceResponse,
    CommercialSeedListingResponse,
    CultivarListResponse,
    CultivarResponse,
    CultivarSourceIdentifierResponse,
    CultivarTraitResponse,
)


def _source_response(source, locator: str) -> CatalogEvidenceSourceResponse:
    return CatalogEvidenceSourceResponse(
        source_document_id=source.id,
        title=source.title,
        publisher=source.publisher,
        source_url=source.source_url,
        sha256=source.sha256,
        retrieved_at=source.retrieved_at,
        license=source.license,
        source_locator=locator,
    )


def _matches(cultivar: Cultivar, query: str) -> bool:
    terms = {
        cultivar.canonical_name.casefold(),
        cultivar.slug.casefold(),
        (cultivar.crop_type or "").replace("_", " ").casefold(),
        *(alias.alias.casefold() for alias in cultivar.aliases),
    }
    return any(query in term for term in terms)


def _match_rank(cultivar: Cultivar, query: str) -> tuple[int, str, str]:
    terms = {
        cultivar.canonical_name.casefold(),
        cultivar.slug.casefold(),
        *(alias.alias.casefold() for alias in cultivar.aliases),
    }
    if query in terms:
        rank = 0
    elif any(term.startswith(query) for term in terms):
        rank = 1
    else:
        rank = 2
    return rank, cultivar.canonical_name.casefold(), cultivar.slug


def list_cultivars(
    session: Session,
    *,
    query: str | None = None,
    crop_slug: str | None = None,
) -> CultivarListResponse:
    dataset = session.scalar(
        select(CultivarDatasetVersion).where(CultivarDatasetVersion.active.is_(True))
    )
    if dataset is None:
        return CultivarListResponse(dataset_id=None, crop_dataset_id=None, cultivars=[])

    cultivars = session.scalars(
        select(Cultivar)
        .where(
            Cultivar.cultivar_dataset_version_id == dataset.id,
            Cultivar.review_status == "approved",
        )
        .options(
            selectinload(Cultivar.crop),
            selectinload(Cultivar.aliases),
            selectinload(Cultivar.source_identifiers).selectinload(
                CultivarSourceIdentifier.source_document
            ),
            selectinload(Cultivar.commercial_listings).selectinload(
                CommercialSeedListing.source_document
            ),
        )
    ).all()
    if crop_slug is not None:
        cultivars = [cultivar for cultivar in cultivars if cultivar.crop.slug == crop_slug]
    normalized_query = query.strip().casefold() if query else None
    if normalized_query:
        cultivars = [cultivar for cultivar in cultivars if _matches(cultivar, normalized_query)]
        cultivars.sort(key=lambda cultivar: _match_rank(cultivar, normalized_query))
    else:
        cultivars.sort(key=lambda cultivar: (cultivar.canonical_name.casefold(), cultivar.slug))

    subject_ids = {cultivar.id for cultivar in cultivars} | {
        cultivar.crop_id for cultivar in cultivars
    }
    claims = (
        session.scalars(
            select(CultivarEvidenceClaim)
            .where(
                CultivarEvidenceClaim.cultivar_dataset_version_id == dataset.id,
                CultivarEvidenceClaim.subject_id.in_(subject_ids),
                CultivarEvidenceClaim.review_status == "approved",
            )
            .options(selectinload(CultivarEvidenceClaim.source_document))
            .order_by(
                CultivarEvidenceClaim.subject_kind,
                CultivarEvidenceClaim.field_name,
                CultivarEvidenceClaim.source_document_id,
            )
        ).all()
        if subject_ids
        else []
    )
    claims_by_subject: dict[str, list[CultivarEvidenceClaim]] = defaultdict(list)
    for claim in claims:
        claims_by_subject[claim.subject_id].append(claim)

    responses: list[CultivarResponse] = []
    for cultivar in cultivars:
        cultivar_claims = claims_by_subject[cultivar.id]
        override_fields = {claim.field_name for claim in cultivar_claims}
        effective_claims = [
            *((claim, False) for claim in cultivar_claims),
            *(
                (claim, True)
                for claim in claims_by_subject[cultivar.crop_id]
                if claim.field_name not in override_fields
            ),
        ]
        effective_claims.sort(key=lambda item: (item[0].field_name, item[1]))
        responses.append(
            CultivarResponse(
                id=cultivar.id,
                slug=cultivar.slug,
                canonical_name=cultivar.canonical_name,
                crop_slug=cultivar.crop.slug,
                crop_name=cultivar.crop.canonical_name,
                crop_type=cultivar.crop_type,
                description=cultivar.description,
                review_status=cultivar.review_status,
                aliases=sorted(alias.alias for alias in cultivar.aliases),
                traits=[
                    CultivarTraitResponse(
                        field_name=claim.field_name,
                        normalized_value=claim.normalized_value,
                        unit=claim.unit,
                        confidence=claim.confidence,
                        inherited_from_crop=inherited,
                        review_status=claim.review_status,
                        source_excerpt=claim.source_excerpt,
                        extraction_method=claim.extraction_method,
                        extractor_version=claim.extractor_version,
                        source=_source_response(claim.source_document, claim.source_locator),
                    )
                    for claim, inherited in effective_claims
                ],
                source_identifiers=[
                    CultivarSourceIdentifierResponse(
                        source_identifier=identifier.source_identifier,
                        name_in_source=identifier.name_in_source,
                        source=_source_response(
                            identifier.source_document,
                            identifier.source_identifier,
                        ),
                    )
                    for identifier in sorted(
                        cultivar.source_identifiers,
                        key=lambda item: (item.source_document_id, item.source_identifier),
                    )
                ],
                commercial_listings=[
                    CommercialSeedListingResponse(
                        id=listing.id,
                        vendor=listing.vendor,
                        listing_name=listing.listing_name,
                        source_identifier=listing.source_identifier,
                        review_status=listing.review_status,
                        source=_source_response(
                            listing.source_document,
                            listing.source_identifier,
                        ),
                    )
                    for listing in sorted(
                        cultivar.commercial_listings,
                        key=lambda item: (item.vendor.casefold(), item.source_identifier),
                    )
                    if listing.review_status == "approved"
                ],
            )
        )
    return CultivarListResponse(
        dataset_id=dataset.id,
        crop_dataset_id=dataset.crop_dataset_version_id,
        cultivars=responses,
    )
