from __future__ import annotations

from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt

from sqlalchemy import select
from sqlalchemy.orm import Session

from kitchen_almanac.db_models import (
    ClimateDatasetVersion,
    ClimateStationNormal,
    GardenProfile,
    LocationEvidenceClaim,
)
from kitchen_almanac.noaa_normals_data import DATASET_KIND, PARSER_VERSION, VARIABLES

MAX_STATION_DISTANCE_KM = 200.0
EARTH_RADIUS_KM = 6371.0088


def haversine_distance_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    latitude_delta = radians(latitude_b - latitude_a)
    longitude_delta = radians(longitude_b - longitude_a)
    start_latitude = radians(latitude_a)
    end_latitude = radians(latitude_b)
    value = sin(latitude_delta / 2) ** 2 + (
        cos(start_latitude) * cos(end_latitude) * sin(longitude_delta / 2) ** 2
    )
    return 2 * EARTH_RADIUS_KM * asin(sqrt(value))


def _confidence(distance_km: float, station: ClimateStationNormal) -> str:
    if distance_km <= 25 and station.completeness_class == "S":
        return "high"
    if distance_km <= 75 and station.completeness_class in {"S", "R"}:
        return "medium"
    return "low"


def enrich_garden_noaa_normals(session: Session, profile: GardenProfile) -> bool:
    if profile.latitude is None or profile.longitude is None:
        return False

    dataset = session.scalar(
        select(ClimateDatasetVersion).where(
            ClimateDatasetVersion.dataset_kind == DATASET_KIND,
            ClimateDatasetVersion.active.is_(True),
        )
    )
    if dataset is None:
        return False

    existing_claim = session.scalar(
        select(LocationEvidenceClaim).where(
            LocationEvidenceClaim.garden_profile_id == profile.id,
            LocationEvidenceClaim.climate_dataset_version_id == dataset.id,
            LocationEvidenceClaim.field_name == "noaa_climate_normals",
        )
    )
    if existing_claim is not None:
        return False

    stations = session.scalars(
        select(ClimateStationNormal).where(
            ClimateStationNormal.climate_dataset_version_id == dataset.id
        )
    ).all()
    if not stations:
        return False

    candidates = [
        (
            haversine_distance_km(
                profile.latitude,
                profile.longitude,
                station.latitude,
                station.longitude,
            ),
            station.station_id,
            station,
        )
        for station in stations
    ]
    distance_km, _, station = min(candidates, key=lambda candidate: candidate[:2])
    if distance_km > MAX_STATION_DISTANCE_KM:
        return False

    source = dataset.source_document
    rounded_distance = round(distance_km, 1)
    session.add(
        LocationEvidenceClaim(
            garden_profile_id=profile.id,
            climate_dataset_version_id=dataset.id,
            field_name="noaa_climate_normals",
            normalized_value={
                "station_id": station.station_id,
                "station_name": station.name,
                "station_latitude": station.latitude,
                "station_longitude": station.longitude,
                "station_elevation_m": station.elevation_m,
                "station_distance_km": rounded_distance,
                "annual_mean_f": station.annual_mean_f,
                "annual_minimum_f": station.annual_minimum_f,
                "annual_maximum_f": station.annual_maximum_f,
                "annual_precipitation_in": station.annual_precipitation_in,
                "growing_degree_days_base_50_f": station.growing_degree_days_base_50_f,
                "last_spring_frost_50": station.last_spring_frost_50,
                "first_fall_frost_50": station.first_fall_frost_50,
                "growing_season_days_50": station.growing_season_days_50,
                "frost_probability": 0.5,
                "completeness_class": station.completeness_class,
                "minimum_years": station.minimum_years,
            },
            unit=None,
            confidence=_confidence(distance_km, station),
            source_document_id=source.id,
            source_excerpt=(
                "1991–2020 station normals; frost dates and season length use the "
                "50-percent probability values for 32°F."
            ),
            source_locator=f"{station.source_locator};variables={','.join(VARIABLES)}",
            extraction_method="nearest_qualifying_station_haversine",
            extractor_version=PARSER_VERSION,
            created_at=datetime.now(UTC),
        )
    )
    session.flush()
    return True


def enrich_all_garden_noaa_normals(session: Session) -> int:
    profiles = session.scalars(
        select(GardenProfile).where(
            GardenProfile.latitude.is_not(None),
            GardenProfile.longitude.is_not(None),
        )
    ).all()
    enriched = sum(enrich_garden_noaa_normals(session, profile) for profile in profiles)
    session.commit()
    return enriched
