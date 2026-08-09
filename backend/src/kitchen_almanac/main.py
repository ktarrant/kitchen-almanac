from __future__ import annotations

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from kitchen_almanac import __version__
from kitchen_almanac.config import get_settings
from kitchen_almanac.database import get_session
from kitchen_almanac.db_models import Crop, DatasetVersion, GardenProfile, Wishlist
from kitchen_almanac.schemas import (
    CatalogSearchResponse,
    ClimateNormalsResponse,
    CropListResponse,
    CropSummary,
    CultivarListResponse,
    EvidenceSourceResponse,
    GardenProfileCreateRequest,
    GardenProfileListResponse,
    GardenProfileResponse,
    HardinessResponse,
    HealthResponse,
    LocationSourceResponse,
    SuitabilityAssessmentResponse,
    WishlistBuilderCreateRequest,
    WishlistCandidateResponse,
    WishlistCreateRequest,
    WishlistCropMatch,
    WishlistCultivarCandidateResponse,
    WishlistCultivarMatch,
    WishlistEntryCreateRequest,
    WishlistEntryResponse,
    WishlistEntryUpdateRequest,
    WishlistResponse,
)
from kitchen_almanac.services.catalog_search_service import (
    CatalogSearchUnavailableError,
    search_catalog,
)
from kitchen_almanac.services.cultivar_service import list_cultivars as query_cultivars
from kitchen_almanac.services.garden_profile_service import (
    GardenProfileNotFoundError,
    create_garden_profile,
    get_garden_profile,
    list_garden_profiles,
)
from kitchen_almanac.services.suitability_service import (
    CultivarNotFoundError,
    SuitabilityUnavailableError,
    get_suitability_assessment,
)
from kitchen_almanac.services.wishlist_service import (
    CatalogUnavailableError,
    InvalidCropSelectionError,
    WishlistNotFoundError,
    add_wishlist_entry,
    create_wishlist,
    create_wishlist_builder,
    get_active_wishlist_for_profile,
    get_wishlist,
    remove_wishlist_entry,
    update_wishlist_entry,
)

app = FastAPI(
    title="Kitchen Almanac",
    version=__version__,
    description="Evidence-backed, location-aware garden planning API.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="kitchen-almanac-api", version=__version__)


@app.get("/api/crops", response_model=CropListResponse)
def list_crops(
    session: Annotated[Session, Depends(get_session)],
    category: Annotated[str | None, Query()] = None,
) -> CropListResponse:
    active_dataset = session.scalar(select(DatasetVersion).where(DatasetVersion.active.is_(True)))
    if active_dataset is None:
        return CropListResponse(dataset_id=None, crops=[])

    query = (
        select(Crop)
        .where(Crop.dataset_version_id == active_dataset.id)
        .options(selectinload(Crop.aliases), selectinload(Crop.appearances))
        .order_by(Crop.canonical_name)
    )
    if category:
        query = query.where(Crop.planning_category == category)

    crops = session.scalars(query).all()
    return CropListResponse(
        dataset_id=active_dataset.id,
        crops=[
            CropSummary(
                slug=crop.slug,
                canonical_name=crop.canonical_name,
                planning_category=crop.planning_category,
                aliases=sorted(alias.alias for alias in crop.aliases),
                seasons=sorted({appearance.season for appearance in crop.appearances}),
            )
            for crop in crops
        ],
    )


@app.get("/api/cultivars", response_model=CultivarListResponse)
def list_cultivars(
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str | None, Query(min_length=1, max_length=120)] = None,
    crop_slug: Annotated[str | None, Query(max_length=100)] = None,
) -> CultivarListResponse:
    return query_cultivars(session, query=q, crop_slug=crop_slug)


@app.get("/api/catalog/search", response_model=CatalogSearchResponse)
def search_catalog_endpoint(
    session: Annotated[Session, Depends(get_session)],
    q: Annotated[str, Query(min_length=1, max_length=120)],
    garden_profile_id: Annotated[str, Query(min_length=36, max_length=36)],
) -> CatalogSearchResponse:
    try:
        return search_catalog(
            session,
            query=q,
            garden_profile_id=garden_profile_id,
        )
    except GardenProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garden profile not found.",
        ) from error
    except CatalogSearchUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


@app.get("/api/suitability", response_model=SuitabilityAssessmentResponse)
def cultivar_suitability_endpoint(
    session: Annotated[Session, Depends(get_session)],
    garden_profile_id: Annotated[str, Query(min_length=36, max_length=36)],
    cultivar_slug: Annotated[str, Query(min_length=1, max_length=100)],
) -> SuitabilityAssessmentResponse:
    try:
        return get_suitability_assessment(
            session,
            garden_profile_id=garden_profile_id,
            cultivar_slug=cultivar_slug,
        )
    except GardenProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garden profile not found.",
        ) from error
    except CultivarNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Cultivar not found in the active catalog.",
        ) from error
    except SuitabilityUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error


def _crop_match(crop: Crop) -> WishlistCropMatch:
    return WishlistCropMatch(
        slug=crop.slug,
        canonical_name=crop.canonical_name,
        planning_category=crop.planning_category,
    )


def _cultivar_match(cultivar) -> WishlistCultivarMatch:
    return WishlistCultivarMatch(
        id=cultivar.id,
        slug=cultivar.slug,
        canonical_name=cultivar.canonical_name,
        crop_slug=cultivar.crop.slug,
        crop_name=cultivar.crop.canonical_name,
        crop_type=cultivar.crop_type,
    )


def _garden_profile_response(profile: GardenProfile) -> GardenProfileResponse:
    location_source = None
    if (
        profile.location_dataset is not None
        and profile.coordinate_source_locator is not None
        and profile.coordinate_method is not None
    ):
        source = profile.location_dataset.source_document
        location_source = LocationSourceResponse(
            dataset_id=profile.location_dataset.id,
            source_document_id=source.id,
            title=source.title,
            publisher=source.publisher,
            source_url=source.source_url,
            sha256=source.sha256,
            retrieved_at=source.retrieved_at,
            source_locator=profile.coordinate_source_locator,
            coordinate_method=profile.coordinate_method,
        )

    def evidence_source(claim) -> EvidenceSourceResponse:
        source = claim.source_document
        return EvidenceSourceResponse(
            dataset_id=claim.climate_dataset_version_id,
            source_document_id=source.id,
            title=source.title,
            publisher=source.publisher,
            source_url=source.source_url,
            sha256=source.sha256,
            retrieved_at=source.retrieved_at,
            license=source.license,
            source_locator=claim.source_locator,
            extraction_method=claim.extraction_method,
            extractor_version=claim.extractor_version,
        )

    hardiness = None
    hardiness_claim = next(
        (claim for claim in profile.location_evidence if claim.field_name == "usda_hardiness"),
        None,
    )
    if hardiness_claim is not None:
        hardiness = HardinessResponse(
            zone=str(hardiness_claim.normalized_value["zone"]),
            mean_annual_extreme_minimum_f=float(
                hardiness_claim.normalized_value["mean_annual_extreme_minimum_f"]
            ),
            confidence=hardiness_claim.confidence,
            source=evidence_source(hardiness_claim),
        )

    climate_normals = None
    climate_claim = next(
        (
            claim
            for claim in profile.location_evidence
            if claim.field_name == "noaa_climate_normals"
        ),
        None,
    )
    if climate_claim is not None:
        value = climate_claim.normalized_value
        climate_normals = ClimateNormalsResponse(
            station_id=str(value["station_id"]),
            station_name=str(value["station_name"]),
            station_latitude=float(value["station_latitude"]),
            station_longitude=float(value["station_longitude"]),
            station_elevation_m=(
                float(value["station_elevation_m"])
                if value["station_elevation_m"] is not None
                else None
            ),
            station_distance_km=float(value["station_distance_km"]),
            annual_mean_f=float(value["annual_mean_f"]),
            annual_minimum_f=float(value["annual_minimum_f"]),
            annual_maximum_f=float(value["annual_maximum_f"]),
            annual_precipitation_in=float(value["annual_precipitation_in"]),
            growing_degree_days_base_50_f=float(value["growing_degree_days_base_50_f"]),
            last_spring_frost_50=str(value["last_spring_frost_50"]),
            first_fall_frost_50=str(value["first_fall_frost_50"]),
            growing_season_days_50=int(value["growing_season_days_50"]),
            frost_probability=float(value["frost_probability"]),
            completeness_class=str(value["completeness_class"]),
            minimum_years=int(value["minimum_years"]),
            confidence=climate_claim.confidence,
            source=evidence_source(climate_claim),
        )
    return GardenProfileResponse(
        id=profile.id,
        name=profile.name,
        country_code=profile.country_code,
        location_input=profile.location_input,
        postal_code=profile.postal_code,
        latitude=profile.latitude,
        longitude=profile.longitude,
        location_status=profile.location_status,
        coordinate_method=profile.coordinate_method,
        location_source=location_source,
        hardiness=hardiness,
        climate_normals=climate_normals,
        target_year=profile.target_year,
        experience_level=profile.experience_level,
        growing_methods=profile.growing_methods,
        support_available=profile.support_available,
        max_plant_spread_inches=profile.max_plant_spread_inches,
        max_container_volume_gallons=profile.max_container_volume_gallons,
        intended_uses=profile.intended_uses,
        disease_concerns=profile.disease_concerns,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _wishlist_response(wishlist: Wishlist) -> WishlistResponse:
    return WishlistResponse(
        id=wishlist.id,
        dataset_id=wishlist.dataset_version_id,
        cultivar_dataset_id=wishlist.cultivar_dataset_version_id,
        garden_profile_id=wishlist.garden_profile_id,
        name=wishlist.name,
        created_at=wishlist.created_at,
        updated_at=wishlist.updated_at,
        entries=[
            WishlistEntryResponse(
                id=entry.id,
                position=entry.position,
                original_text=entry.original_text,
                normalized_text=entry.normalized_text,
                status=entry.status,
                resolution_method=entry.resolution_method,
                intent_kind=entry.intent_kind,
                cultivar_intent_text=entry.cultivar_intent_text,
                crop_type_intent=entry.crop_type_intent,
                resolved_crop=_crop_match(entry.resolved_crop) if entry.resolved_crop else None,
                resolved_cultivar=(
                    _cultivar_match(entry.resolved_cultivar) if entry.resolved_cultivar else None
                ),
                candidates=[
                    WishlistCandidateResponse(
                        **_crop_match(candidate.crop).model_dump(),
                        score=candidate.score,
                        matched_alias=candidate.matched_alias,
                    )
                    for candidate in entry.candidates
                ],
                cultivar_candidates=[
                    WishlistCultivarCandidateResponse(
                        **_cultivar_match(candidate.cultivar).model_dump(),
                        score=candidate.score,
                        matched_alias=candidate.matched_alias,
                    )
                    for candidate in entry.cultivar_candidates
                ],
            )
            for entry in wishlist.entries
        ],
    )


@app.post(
    "/api/garden-profiles",
    response_model=GardenProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_garden_profile_endpoint(
    request: GardenProfileCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> GardenProfileResponse:
    return _garden_profile_response(create_garden_profile(session, request))


@app.get("/api/garden-profiles", response_model=GardenProfileListResponse)
def list_garden_profiles_endpoint(
    session: Annotated[Session, Depends(get_session)],
) -> GardenProfileListResponse:
    return GardenProfileListResponse(
        profiles=[_garden_profile_response(profile) for profile in list_garden_profiles(session)]
    )


@app.get("/api/garden-profiles/{profile_id}", response_model=GardenProfileResponse)
def get_garden_profile_endpoint(
    profile_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> GardenProfileResponse:
    try:
        profile = get_garden_profile(session, profile_id)
    except GardenProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garden profile not found.",
        ) from error
    return _garden_profile_response(profile)


@app.get(
    "/api/garden-profiles/{profile_id}/wishlists/active",
    response_model=WishlistResponse | None,
)
def get_active_profile_wishlist_endpoint(
    profile_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> WishlistResponse | None:
    try:
        wishlist = get_active_wishlist_for_profile(session, profile_id)
    except GardenProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garden profile not found.",
        ) from error
    return _wishlist_response(wishlist) if wishlist else None


@app.post(
    "/api/wishlists",
    response_model=WishlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wishlist_endpoint(
    request: WishlistCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> WishlistResponse:
    try:
        wishlist = create_wishlist(
            session,
            text=request.text,
            garden_profile_id=request.garden_profile_id,
            name=request.name.strip(),
        )
    except CatalogUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except GardenProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garden profile not found.",
        ) from error
    return _wishlist_response(wishlist)


@app.post(
    "/api/wishlists/builder",
    response_model=WishlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_wishlist_builder_endpoint(
    request: WishlistBuilderCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> WishlistResponse:
    try:
        wishlist = create_wishlist_builder(
            session,
            garden_profile_id=request.garden_profile_id,
            name=request.name,
        )
    except CatalogUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except GardenProfileNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Garden profile not found.",
        ) from error
    return _wishlist_response(wishlist)


@app.post(
    "/api/wishlists/{wishlist_id}/entries",
    response_model=WishlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_wishlist_entry_endpoint(
    wishlist_id: str,
    request: WishlistEntryCreateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> WishlistResponse:
    try:
        wishlist = add_wishlist_entry(
            session,
            wishlist_id=wishlist_id,
            original_text=request.original_text,
            selection_kind=request.selection_kind,
            crop_slug=request.crop_slug,
            cultivar_slug=request.cultivar_slug,
        )
    except WishlistNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found.",
        ) from error
    except InvalidCropSelectionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The selected crop or cultivar is not in this wishlist's catalog.",
        ) from error
    return _wishlist_response(wishlist)


@app.get("/api/wishlists/{wishlist_id}", response_model=WishlistResponse)
def get_wishlist_endpoint(
    wishlist_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> WishlistResponse:
    try:
        wishlist = get_wishlist(session, wishlist_id)
    except WishlistNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist not found.",
        ) from error
    return _wishlist_response(wishlist)


@app.patch(
    "/api/wishlists/{wishlist_id}/entries/{entry_id}",
    response_model=WishlistResponse,
)
def update_wishlist_entry_endpoint(
    wishlist_id: str,
    entry_id: str,
    request: WishlistEntryUpdateRequest,
    session: Annotated[Session, Depends(get_session)],
) -> WishlistResponse:
    try:
        wishlist = update_wishlist_entry(
            session,
            wishlist_id=wishlist_id,
            entry_id=entry_id,
            crop_slug=request.crop_slug,
            cultivar_slug=request.cultivar_slug,
            keep_custom=request.keep_custom,
        )
    except WishlistNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist entry not found.",
        ) from error
    except InvalidCropSelectionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="The selected crop or cultivar is not in this wishlist's catalog.",
        ) from error
    return _wishlist_response(wishlist)


@app.delete(
    "/api/wishlists/{wishlist_id}/entries/{entry_id}",
    response_model=WishlistResponse,
)
def remove_wishlist_entry_endpoint(
    wishlist_id: str,
    entry_id: str,
    session: Annotated[Session, Depends(get_session)],
) -> WishlistResponse:
    try:
        wishlist = remove_wishlist_entry(
            session,
            wishlist_id=wishlist_id,
            entry_id=entry_id,
        )
    except WishlistNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wishlist entry not found.",
        ) from error
    return _wishlist_response(wishlist)
