from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from kitchen_almanac.db_models import GardenProfile
from kitchen_almanac.schemas import GardenProfileCreateRequest


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
    else:
        assert request.latitude is not None
        assert request.longitude is not None
        location_input = f"{request.latitude:.6f},{request.longitude:.6f}"
        postal_code = None
        latitude = request.latitude
        longitude = request.longitude
        location_status = "coordinates_provided"

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
        target_year=request.target_year,
        experience_level=request.experience_level,
        growing_methods=[method.value for method in request.growing_methods],
        created_at=now,
        updated_at=now,
    )
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


def get_garden_profile(session: Session, profile_id: str) -> GardenProfile:
    profile = session.get(GardenProfile, profile_id)
    if profile is None:
        raise GardenProfileNotFoundError(profile_id)
    return profile
