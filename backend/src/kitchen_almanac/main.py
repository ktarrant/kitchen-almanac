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
    CropListResponse,
    CropSummary,
    GardenProfileCreateRequest,
    GardenProfileResponse,
    HealthResponse,
    LocationSourceResponse,
    WishlistCandidateResponse,
    WishlistCreateRequest,
    WishlistCropMatch,
    WishlistEntryResponse,
    WishlistEntryUpdateRequest,
    WishlistResponse,
)
from kitchen_almanac.services.garden_profile_service import (
    GardenProfileNotFoundError,
    create_garden_profile,
    get_garden_profile,
)
from kitchen_almanac.services.wishlist_service import (
    CatalogUnavailableError,
    InvalidCropSelectionError,
    WishlistNotFoundError,
    create_wishlist,
    get_wishlist,
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


def _crop_match(crop: Crop) -> WishlistCropMatch:
    return WishlistCropMatch(
        slug=crop.slug,
        canonical_name=crop.canonical_name,
        planning_category=crop.planning_category,
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
        target_year=profile.target_year,
        experience_level=profile.experience_level,
        growing_methods=profile.growing_methods,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _wishlist_response(wishlist: Wishlist) -> WishlistResponse:
    return WishlistResponse(
        id=wishlist.id,
        dataset_id=wishlist.dataset_version_id,
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
                resolved_crop=_crop_match(entry.resolved_crop) if entry.resolved_crop else None,
                candidates=[
                    WishlistCandidateResponse(
                        **_crop_match(candidate.crop).model_dump(),
                        score=candidate.score,
                        matched_alias=candidate.matched_alias,
                    )
                    for candidate in entry.candidates
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
            detail="The selected crop is not in this wishlist's catalog.",
        ) from error
    return _wishlist_response(wishlist)
