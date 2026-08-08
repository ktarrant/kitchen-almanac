from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from kitchen_almanac.db_models import GardenProfile, LocationDatasetVersion, PostalCodeLocation
from kitchen_almanac.schemas import GardenProfileCreateRequest
from kitchen_almanac.services.hardiness_service import enrich_garden_hardiness
from kitchen_almanac.services.noaa_normals_service import enrich_garden_noaa_normals


class GardenProfileNotFoundError(LookupError):
    pass


def create_garden_profile(
    session: Session,
    request: GardenProfileCreateRequest,
) -> GardenProfile:
    if request.postal_code is not None:
        location_input = request.postal_code
        postal_code = request.postal_code[:5]
        latitude = None
        longitude = None
        location_status = "postal_code_pending"
        location_dataset_version_id = None
        coordinate_method = None
        coordinate_source_locator = None

        postal_location = session.scalar(
            select(PostalCodeLocation)
            .join(LocationDatasetVersion)
            .where(
                LocationDatasetVersion.active.is_(True),
                PostalCodeLocation.postal_code == postal_code,
            )
        )
        if postal_location is not None:
            latitude = postal_location.latitude
            longitude = postal_location.longitude
            location_status = "postal_code_resolved"
            location_dataset_version_id = postal_location.location_dataset_version_id
            coordinate_method = postal_location.coordinate_method
            coordinate_source_locator = postal_location.source_locator
    else:
        assert request.latitude is not None
        assert request.longitude is not None
        location_input = f"{request.latitude:.6f},{request.longitude:.6f}"
        postal_code = None
        latitude = request.latitude
        longitude = request.longitude
        location_status = "coordinates_provided"
        location_dataset_version_id = None
        coordinate_method = "user_provided"
        coordinate_source_locator = None

    now = datetime.now(UTC)
    profile = GardenProfile(
        id=str(uuid4()),
        name=request.name,
        country_code=request.country_code,
        location_input=location_input,
        postal_code=postal_code,
        latitude=latitude,
        longitude=longitude,
        location_status=location_status,
        location_dataset_version_id=location_dataset_version_id,
        coordinate_method=coordinate_method,
        coordinate_source_locator=coordinate_source_locator,
        target_year=request.target_year,
        experience_level=request.experience_level,
        growing_methods=[method.value for method in request.growing_methods],
        support_available=request.support_available,
        max_plant_spread_inches=request.max_plant_spread_inches,
        max_container_volume_gallons=request.max_container_volume_gallons,
        intended_uses=[item.value for item in request.intended_uses],
        disease_concerns=[item.value for item in request.disease_concerns],
        created_at=now,
        updated_at=now,
    )
    session.add(profile)
    session.flush()
    enrich_garden_hardiness(session, profile)
    enrich_garden_noaa_normals(session, profile)
    session.commit()
    session.refresh(profile)
    return profile


def get_garden_profile(session: Session, profile_id: str) -> GardenProfile:
    profile = session.get(GardenProfile, profile_id)
    if profile is None:
        raise GardenProfileNotFoundError(profile_id)
    return profile
